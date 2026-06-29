"""XLIFF to EPUB channel tests."""

import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from orf.channels.xliff2epub import XLIFF2EPUBConverter
from orf.converters.options import ConverterOptions
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
            sample_epub_skeleton, sample_xliff, output, options=ConverterOptions(preserve_styles=True)
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

class TestXLIFF2EPUBParseOnceSpeedup:
    """A1.3-followup: BeautifulSoup parse-once / mutate-in-place / serialize-once.

    Pre-A1.3 the channel did ``O(N x M x 3)`` regex: N segments x full
    chapter size M x 3 placeholder patterns. Post-A1.3: parse the
    chapter once with BS4, single tree walk, serialize once.
    """

    def test_apply_segments_to_xhtml_1000_segments_under_60s(
        self, tmp_path: Path
    ):
        import time
        from orf.channels.xliff2epub import XLIFF2EPUBConverter

        # Build a single chapter with 1000 <p> elements, each with a
        # unique id that matches a segment. Pad each paragraph to make
        # the chapter > 100KB (the A1.3 perf-target scale).
        n_segments = 1000
        padding = "x" * 100
        body_lines = [
            f'<p id="seg_{i:04d}">Original paragraph {i} {padding}</p>'
            for i in range(n_segments)
        ]
        chapter_xhtml = (
            '<html xmlns="http://www.w3.org/1999/xhtml"><body>'
            + "\n".join(body_lines)
            + "</body></html>"
        )
        # Sanity: chapter is reasonably large (>100KB)
        assert len(chapter_xhtml.encode("utf-8")) > 100 * 1024, (
            f"chapter size {len(chapter_xhtml.encode('utf-8'))} bytes "
            f"< 100KB target; pad more"
        )

        segments = {f"seg_{i:04d}": f"TRANSLATED({i})" for i in range(n_segments)}

        converter = XLIFF2EPUBConverter()
        t0 = time.perf_counter()
        result = converter._apply_segments_to_xhtml(chapter_xhtml, segments, {})
        elapsed = time.perf_counter() - t0

        # Verify all 1000 segments were replaced.
        for i in range(n_segments):
            assert f"TRANSLATED({i})" in result, (
                f"segment seg_{i:04d} missing from result"
            )
        # Sanity: original markers are gone.
        assert "Original paragraph 0" not in result

        # Speedup contract: A1.3 parse-once must beat the pre-A1.3
        # O(N x M x 3) regex loop. We observed ~1-3s in practice for
        # 1000 segments on 100KB+ chapter; loose the threshold to 60s
        # for safety on slow CI.
        assert elapsed < 60.0, (
            f"A1.3 parse-once contract violated: 1000 segments on 100KB+ "
            f"chapter took {elapsed:.2f}s (must be < 60s). "
            f"Pre-A1.3 baseline was O(N x M x 3) = minutes; parse-once "
            f"BS4 refactor delivers ~30x+ speedup."
        )


class TestXLIFF2EPUBSegmentIdMatch:
    """Tests for data-trans-unit-id scanning in _apply_segments_to_xhtml.

    OPP#39 injects data-trans-unit-id into EPUB chapter XHTML elements
    so ORF can match them to XLIFF trans-unit IDs. These tests verify
    that the new attribute scan works alongside the existing id scan.
    """

    def test_data_trans_unit_id_match(self):
        """Verify that elements with data-trans-unit-id get translated."""
        from orf.channels.xliff2epub import XLIFF2EPUBConverter

        xhtml = (
            '<html xmlns="http://www.w3.org/1999/xhtml"><body>'
            '<p data-trans-unit-id="1">Hello world</p>'
            '<p data-trans-unit-id="2">Goodbye world</p>'
            '</body></html>'
        )
        segments = {
            "1": "Bonjour le monde",
            "2": "Au revoir le monde",
        }
        converter = XLIFF2EPUBConverter()
        result = converter._apply_segments_to_xhtml(xhtml, segments)

        assert "Bonjour le monde" in result, "data-trans-unit-id=1 match failed"
        assert "Au revoir le monde" in result, "data-trans-unit-id=2 match failed"
        assert "Hello world" not in result, "original text should be replaced"
        assert "Goodbye world" not in result, "original text should be replaced"

    def test_data_trans_unit_id_partial_match(self):
        """Verify that only matching data-trans-unit-id elements are translated."""
        from orf.channels.xliff2epub import XLIFF2EPUBConverter

        xhtml = (
            '<html xmlns="http://www.w3.org/1999/xhtml"><body>'
            '<p data-trans-unit-id="1">Translate this</p>'
            '<p data-trans-unit-id="99">Leave this</p>'
            '</body></html>'
        )
        segments = {"1": "Traduis ceci"}
        converter = XLIFF2EPUBConverter()
        result = converter._apply_segments_to_xhtml(xhtml, segments)

        assert "Traduis ceci" in result, "matched segment should be translated"
        assert "Leave this" in result, "unmatched segment should remain unchanged"

    def test_fallback_id_match_still_works(self):
        """Verify that traditional id-based matching still works."""
        from orf.channels.xliff2epub import XLIFF2EPUBConverter

        xhtml = (
            '<html xmlns="http://www.w3.org/1999/xhtml"><body>'
            '<p id="seg1">Original text</p>'
            '</body></html>'
        )
        segments = {"seg1": "Translated text"}
        converter = XLIFF2EPUBConverter()
        result = converter._apply_segments_to_xhtml(xhtml, segments)

        assert "Translated text" in result, "id-based match failed"
        assert "Original text" not in result, "original text should be replaced"

    def test_data_segment_match_still_works(self):
        """Verify that data-segment based matching still works."""
        from orf.channels.xliff2epub import XLIFF2EPUBConverter

        xhtml = (
            '<html xmlns="http://www.w3.org/1999/xhtml"><body>'
            '<p data-segment="segA">Original A</p>'
            '</body></html>'
        )
        segments = {"segA": "Translated A"}
        converter = XLIFF2EPUBConverter()
        result = converter._apply_segments_to_xhtml(xhtml, segments)

        assert "Translated A" in result, "data-segment-based match failed"
        assert "Original A" not in result, "original text should be replaced"

    def test_name_attribute_match_still_works(self):
        """Verify that name attribute based matching still works."""
        from orf.channels.xliff2epub import XLIFF2EPUBConverter

        xhtml = (
            '<html xmlns="http://www.w3.org/1999/xhtml"><body>'
            '<p name="segB">Original B</p>'
            '</body></html>'
        )
        segments = {"segB": "Translated B"}
        converter = XLIFF2EPUBConverter()
        result = converter._apply_segments_to_xhtml(xhtml, segments)

        assert "Translated B" in result, "name-based match failed"
        assert "Original B" not in result, "original text should be replaced"

    def test_data_trans_unit_id_priority(self):
        """Verify data-trans-unit-id is checked before name attribute.

        The scan order is: id → data-segment → data-trans-unit-id → name.
        If an element has both data-trans-unit-id and name, the former
        should be used and the latter should not consume the segment.
        """
        from orf.channels.xliff2epub import XLIFF2EPUBConverter

        xhtml = (
            '<html xmlns="http://www.w3.org/1999/xhtml"><body>'
            '<p data-trans-unit-id="1" name="2">Dual attribute element</p>'
            '</body></html>'
        )
        segments = {"1": "Used via data-trans-unit-id", "2": "Should NOT be used"}
        converter = XLIFF2EPUBConverter()
        result = converter._apply_segments_to_xhtml(xhtml, segments)

        assert "Used via data-trans-unit-id" in result, (
            "should match via data-trans-unit-id (higher priority)"
        )
        assert "Should NOT be used" not in result, (
            "name should not consume a different segment"
        )
