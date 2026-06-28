"""Regression tests for the xliff2docx package split (Task 3.4).

Verifies that after splitting the monolithic ``xliff2docx.py`` into a
6-module package, all public names, function signatures, and behaviors
are preserved identically.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

# ── Test 1: Main class import ────────────────────────────────────────────────


class TestPackageImports:
    """Verify all public names are importable from the package."""

    def test_class_import(self):
        """XLIFF2DOCXConverter is importable from the expected path."""
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        assert XLIFF2DOCXConverter is not None

    def test_helper_function_imports(self):
        """Helper functions are importable from the package."""
        from orf.channels.xliff2docx import (
            _strip_wrapper,
            _strip_inline_tags,
            _distribute_text_across_runs,
        )

        assert callable(_strip_wrapper)
        assert callable(_strip_inline_tags)
        assert callable(_distribute_text_across_runs)

    def test_constant_import(self):
        """FUZZY_MATCH_THRESHOLD is importable from the package."""
        from orf.channels.xliff2docx import FUZZY_MATCH_THRESHOLD

        assert FUZZY_MATCH_THRESHOLD == 0.70

    def test_namespace_imports(self):
        """Namespace constants are importable from the package."""
        from orf.channels.xliff2docx import A_NS, PIC_NS, W_NS, WP_NS

        assert A_NS == "http://schemas.openxmlformats.org/drawingml/2006/main"
        assert PIC_NS == "http://schemas.openxmlformats.org/drawingml/2006/picture"
        assert W_NS == "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        assert WP_NS == "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"

    def test_dataclass_imports(self):
        """Dataclasses are importable from the package."""
        from orf.channels.xliff2docx import XLIFFTransUnitData, InlineElementData

        tu = XLIFFTransUnitData(id="1", source="hello")
        assert tu.id == "1"
        assert tu.source == "hello"

        ie = InlineElementData(id="bx1", type="bold", begin_pos=0, end_pos=5)
        assert ie.type == "bold"


# ── Test 2: Submodule imports ────────────────────────────────────────────────


class TestSubmoduleImports:
    """Verify each submodule can be imported directly."""

    def test_ns_module(self):
        from orf.channels.xliff2docx._ns import (
            W_NS, WORD_NS_MAP, FUZZY_MATCH_THRESHOLD,
            ALLOWED_RELATIVE_FROM,
        )

        assert "page" in ALLOWED_RELATIVE_FROM
        assert W_NS in str(WORD_NS_MAP)

    def test_parser_module(self):
        from orf.channels.xliff2docx.parser import (
            parse_xliff, extract_inline_elements_from_xml,
            _strip_wrapper, _strip_inline_tags,
        )

        assert callable(parse_xliff)
        assert callable(extract_inline_elements_from_xml)
        assert callable(_strip_wrapper)

    def test_matcher_module(self):
        from orf.channels.xliff2docx.matcher import (
            backfill_translation, fuzzy_backfill,
            backfill_split_runs, backfill_by_position,
            backfill_by_non_body_position, collect_all_paragraphs,
            backfill_fallback_textboxes, fallback_backfill,
            backfill_with_inline_elements,
            _distribute_text_across_runs,
        )

        assert callable(backfill_translation)
        assert callable(fuzzy_backfill)
        assert callable(backfill_split_runs)

    def test_writer_module(self):
        from orf.channels.xliff2docx.writer import build_formatted_runs

        assert callable(build_formatted_runs)

    def test_styles_module(self):
        from orf.channels.xliff2docx.styles import (
            apply_inline_formatting_to_run,
            build_inline_format_map,
        )

        assert callable(apply_inline_formatting_to_run)

    def test_images_module(self):
        from orf.channels.xliff2docx.images import (
            inject_images_into_docx, get_image_bytes,
            get_image_dimensions, add_image_to_zip,
            create_drawing_xml, create_floating_anchor_xml,
            paragraph_already_has_drawing, inject_floating_image,
        )

        assert callable(inject_images_into_docx)
        assert callable(get_image_bytes)


# ── Test 3: XLIFF2DOCXConverter API parity ───────────────────────────────────


class TestConverterAPI:
    """Verify the converter class API is identical to pre-split."""

    def test_init_creates_dependencies(self):
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()
        assert converter.skeleton_loader is not None
        assert converter.inline_parser is not None
        assert converter.docx_applier is not None

    def test_supported_format(self):
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()
        assert converter.supported_format == "DOCX"

    def test_validate_input_valid_docx(self, tmp_path):
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        path = tmp_path / "test.docx"
        path.write_bytes(b"PK\x03\x04")  # ZIP magic
        converter = XLIFF2DOCXConverter()
        assert converter.validate_input(str(path)) is True

    def test_validate_input_valid_zip(self, tmp_path):
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        path = tmp_path / "test.zip"
        path.write_bytes(b"PK\x03\x04")
        converter = XLIFF2DOCXConverter()
        assert converter.validate_input(str(path)) is True

    def test_validate_input_invalid_extension(self, tmp_path):
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        path = tmp_path / "test.txt"
        path.write_text("hello")
        converter = XLIFF2DOCXConverter()
        assert converter.validate_input(str(path)) is False

    def test_validate_input_not_exists(self):
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()
        assert converter.validate_input("/nonexistent/foo.docx") is False

    def test_all_methods_exist(self):
        """All expected methods are present on the class."""
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        expected_methods = [
            "_parse_xliff",
            "_extract_inline_elements",
            "_backfill_translation",
            "_fuzzy_backfill",
            "_backfill_by_position",
            "_collect_all_paragraphs",
            "_backfill_by_non_body_position",
            "_backfill_fallback_textboxes",
            "_fallback_backfill",
            "_backfill_with_inline_elements",
            "_backfill_split_runs",
            "_build_formatted_runs",
            "_apply_inline_formatting_to_run",
            "inject_images",
            "_paragraph_already_has_drawing",
            "_inject_floating_image",
            "_create_floating_anchor_xml",
            "_get_image_bytes",
            "_get_image_dimensions",
            "_add_image_to_zip",
            "_create_drawing_xml",
        ]
        for method in expected_methods:
            assert hasattr(XLIFF2DOCXConverter, method), f"Missing method: {method}"


# ── Test 4: Helper function behavior parity ──────────────────────────────────


class TestHelperFunctions:
    """Verify helper functions behave identically to the original."""

    def test_strip_wrapper_noop(self):
        from orf.channels.xliff2docx import _strip_wrapper

        assert _strip_wrapper("plain text") == "plain text"

    def test_strip_wrapper_removes_source_tag(self):
        from orf.channels.xliff2docx import _strip_wrapper

        result = _strip_wrapper(
            '<source xmlns="urn:oasis:names:tc:xliff:document:1.2">hello</source>'
        )
        assert result == "hello"

    def test_strip_wrapper_compound(self):
        from orf.channels.xliff2docx import _strip_wrapper

        result = _strip_wrapper('a</source>\n\n<source>b</source>')
        # Tags removed but internal whitespace preserved (strip() only
        # removes leading/trailing, not between content)
        assert result == "a\n\nb"

    def test_strip_inline_tags_strips_bx(self):
        from orf.channels.xliff2docx import _strip_inline_tags

        assert _strip_inline_tags('<bx id="1" type="bold"/>hello') == "hello"

    def test_strip_inline_tags_strips_ex(self):
        from orf.channels.xliff2docx import _strip_inline_tags

        assert _strip_inline_tags('hello<ex id="1"/>') == "hello"

    def test_strip_inline_tags_idempotent(self):
        from orf.channels.xliff2docx import _strip_inline_tags

        text = '<bx id="1" type="bold"/>hello<ex id="1"/>'
        assert _strip_inline_tags(text) == _strip_inline_tags(_strip_inline_tags(text))

    def test_distribute_text_across_runs(self):
        from orf.channels.xliff2docx import _distribute_text_across_runs
        from lxml import etree

        runs = [etree.Element("t"), etree.Element("t")]
        _distribute_text_across_runs(runs, "hello\nworld")
        assert runs[0].text == "hello"
        assert runs[1].text == "world"

    def test_distribute_text_extra_runs_cleared(self):
        from orf.channels.xliff2docx import _distribute_text_across_runs
        from lxml import etree

        runs = [etree.Element("t"), etree.Element("t"), etree.Element("t")]
        runs[0].text = "old1"
        runs[1].text = "old2"
        runs[2].text = "old3"
        _distribute_text_across_runs(runs, "single")
        assert runs[0].text == "single"
        assert runs[1].text == ""
        assert runs[2].text == ""


# ── Test 5: Parser function behavior ─────────────────────────────────────────


class TestParserFunctions:
    """Verify parser functions work correctly."""

    def test_parse_xliff_raises_on_nonexistent(self):
        from orf.channels.xliff2docx.parser import parse_xliff
        from orf.error_handlers.conversion_error import XLIFFParseError

        with pytest.raises(XLIFFParseError):
            parse_xliff("/nonexistent/file.xlf", None)

    def test_extract_inline_elements_empty(self):
        from orf.channels.xliff2docx.parser import extract_inline_elements_from_xml

        result = extract_inline_elements_from_xml("", None)
        assert result == []


# ── Test 6: Matcher function behavior ────────────────────────────────────────


class TestMatcherFunctions:
    """Verify matcher functions preserve E2E-07 fuzzy algorithm."""

    def test_fallback_backfill_returns_false(self):
        from orf.channels.xliff2docx.matcher import fallback_backfill

        assert fallback_backfill("some text") is False

    def test_collect_all_paragraphs_empty_root(self):
        from orf.channels.xliff2docx.matcher import collect_all_paragraphs
        from lxml import etree

        root = etree.fromstring(
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body></w:body></w:document>'
        )
        paragraphs = collect_all_paragraphs(root)
        assert paragraphs == []


# ── Test 7: Writer function behavior ─────────────────────────────────────────


class TestWriterFunctions:
    """Verify writer functions preserve formatting logic."""

    def test_build_formatted_runs_plain_text(self):
        from orf.channels.xliff2docx.writer import build_formatted_runs

        result = build_formatted_runs("plain text")
        assert result == []

    def test_build_formatted_runs_with_bold(self):
        from orf.channels.xliff2docx.writer import build_formatted_runs

        result = build_formatted_runs(
            '<bx id="1" type="bold"/>bold text<ex id="1"/>'
        )
        assert len(result) >= 1


# ── Test 8: Image function behavior ──────────────────────────────────────────


class TestImageFunctions:
    """Verify image functions work correctly."""

    def test_create_drawing_xml_contains_inline(self):
        from orf.channels.xliff2docx.images import create_drawing_xml

        xml = create_drawing_xml("rId1", 100, 200)
        assert "wp:inline" in xml
        assert "rId1" in xml
        assert 'cx="100"' in xml
        assert 'cy="200"' in xml

    def test_paragraph_already_has_drawing_no_match(self):
        from orf.channels.xliff2docx.images import paragraph_already_has_drawing
        from lxml import etree

        root = etree.fromstring(
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
            ' xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
            '<w:body><w:p></w:p></w:body></w:document>'
        )
        assert paragraph_already_has_drawing(root, 100, 200) is False

    def test_get_image_bytes_data_base64(self):
        from orf.channels.xliff2docx.images import get_image_bytes
        from orf.mcp.schemas import ImagePlacement
        import base64

        img = ImagePlacement(
            data_base64=base64.b64encode(b"test image data").decode(),
            mime_type="image/png",
        )
        result = get_image_bytes(img)
        assert result == b"test image data"

    def test_get_image_bytes_raises_on_empty(self):
        from orf.channels.xliff2docx.images import get_image_bytes
        from orf.mcp.schemas import ImagePlacement

        with pytest.raises(ValueError, match="ImagePlacement must have"):
            get_image_bytes(ImagePlacement(mime_type="image/png"))

    def test_create_floating_anchor_xml_validates_relative(self):
        from orf.channels.xliff2docx.images import create_floating_anchor_xml

        with pytest.raises(ValueError, match="relative_h"):
            create_floating_anchor_xml(
                "rId1", 100, 200, 0, 0,
                relative_h="invalid_value",
            )

    def test_create_floating_anchor_xml_success(self):
        from orf.channels.xliff2docx.images import create_floating_anchor_xml

        xml = create_floating_anchor_xml("rId1", 100, 200, 5000, 3000)
        assert "wp:anchor" in xml
        assert "rId1" in xml


# ── Test 9: Error type import parity ─────────────────────────────────────────


class TestErrorImportParity:
    """Verify XLIFFParseError is importable from the package."""

    def test_xliff_parse_error_import(self):
        from orf.channels.xliff2docx import XLIFFParseError
        from orf.error_handlers.conversion_error import XLIFFParseError as OrigError

        assert XLIFFParseError is OrigError


# ── Test 10: Legacy xliff2docx.py shim ────────────────────────────────────────


class TestLegacyShim:
    """Verify the old file path still works as a re-export, or is absent."""

    def test_old_file_moved_to_backup(self):
        """The old xliff2docx.py should be moved away (package takes over)."""
        old_path = Path(__file__).parent.parent / "src/orf/channels/xliff2docx.py"
        assert not old_path.exists(), (
            "Old xliff2docx.py should be removed; "
            "package at xliff2docx/ replaces it"
        )


# ── Test 11: Delegation method signatures match submodule functions ──────────


class TestDelegationSignatures:
    """Verify delegate methods pass correct args to submodule functions."""

    def test_strip_wrapper_same_in_parser_and_package(self):
        from orf.channels.xliff2docx import _strip_wrapper as pkg_sw
        from orf.channels.xliff2docx.parser import _strip_wrapper as mod_sw

        # Both reference the same function
        assert pkg_sw is mod_sw

    def test_distribute_text_same_in_matcher_and_package(self):
        from orf.channels.xliff2docx import _distribute_text_across_runs as pkg_dt
        from orf.channels.xliff2docx.matcher import _distribute_text_across_runs as mod_dt

        assert pkg_dt is mod_dt


# ── Test 12: Edge cases for helper functions ──────────────────────────────────


class TestEdgeCases:
    """Edge case tests for helper functions."""

    def test_strip_wrapper_empty_string(self):
        from orf.channels.xliff2docx import _strip_wrapper

        assert _strip_wrapper("") == ""

    def test_strip_wrapper_only_tags(self):
        from orf.channels.xliff2docx import _strip_wrapper

        result = _strip_wrapper("<source>text</source>")
        assert result == "text"

    def test_strip_inline_tags_empty(self):
        from orf.channels.xliff2docx import _strip_inline_tags

        assert _strip_inline_tags("") == ""

    def test_strip_inline_tags_no_tags(self):
        from orf.channels.xliff2docx import _strip_inline_tags

        assert _strip_inline_tags("plain text") == "plain text"

    def test_distribute_text_empty(self):
        from orf.channels.xliff2docx import _distribute_text_across_runs
        from lxml import etree

        runs = [etree.Element("t")]
        _distribute_text_across_runs(runs, "")
        assert runs[0].text == ""

    def test_distribute_text_exact_lines_to_runs(self):
        from orf.channels.xliff2docx import _distribute_text_across_runs
        from lxml import etree

        runs = [etree.Element("t"), etree.Element("t"), etree.Element("t")]
        _distribute_text_across_runs(runs, "line1\nline2\nline3")
        assert runs[0].text == "line1"
        assert runs[1].text == "line2"
        assert runs[2].text == "line3"
