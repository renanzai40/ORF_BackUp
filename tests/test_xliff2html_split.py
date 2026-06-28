"""Regression tests for XLIFF2HTML converter split into sub-modules.

Verifies that:
1. The XLIFF2HTMLConverter class still produces correct HTML output
2. All sub-modules are importable
3. The parser, writer, and images functions work correctly
"""

from __future__ import annotations

from pathlib import Path

import pytest

from orf.channels.xliff2html import XLIFF2HTMLConverter
from orf.channels.xliff2html.parser import parse_xliff, strip_xliff_inline_tags
from orf.channels.xliff2html.writer import (
    parse_html_fragment,
    wrap_translation_with_xliff_inline,
    inject_translations_into_dom,
)
from orf.channels.xliff2html.images import get_image_bytes, create_data_uri
from orf.converters.options import ConverterOptions
from orf.mcp.schemas import ImagePlacement

# Sentinel used in the module for inline translation
_INLINE_TRANSLATION_SENTINEL = "\x00TRANSLATED_TEXT\x00"


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sample_html_template(tmp_path: Path) -> Path:
    """Simple HTML template with data-trans-unit-id attributes."""
    content = """<!DOCTYPE html>
<html>
<head><title>Test Document</title></head>
<body>
<h1 data-trans-unit-id="heading1">Original Heading</h1>
<p data-trans-unit-id="para1">Original paragraph content.</p>
<p data-trans-unit-id="trans-unit-1">placeholder one</p>
<p data-trans-unit-id="trans-unit-2">placeholder two</p>
</body>
</html>"""
    html_file = tmp_path / "template.html"
    html_file.write_text(content, encoding="utf-8")
    return html_file


@pytest.fixture
def sample_xliff(tmp_path: Path) -> Path:
    """Standard XLIFF with 4 translation units."""
    content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
<file original="template.html" source-language="en" target-language="zh-CN">
<body>
<trans-unit id="heading1">
<source>Original Heading</source>
<target>翻译标题</target>
</trans-unit>
<trans-unit id="para1">
<source>Original paragraph content.</source>
<target>翻译的段落内容。</target>
</trans-unit>
<trans-unit id="trans-unit-1">
<source>placeholder 1</source>
<target>占位符1</target>
</trans-unit>
<trans-unit id="trans-unit-2">
<source>placeholder 2</source>
<target>占位符2</target>
</trans-unit>
</body>
</file>
</xliff>"""
    xliff_file = tmp_path / "translation.xlf"
    xliff_file.write_text(content, encoding="utf-8")
    return xliff_file


@pytest.fixture
def xliff_with_inline_tags(tmp_path: Path) -> Path:
    """XLIFF with <bx/> and <ex/> inline formatting tags."""
    content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
<file original="template.html" source-language="en" target-language="zh-CN">
<body>
<trans-unit id="para-bold">
<source>Plain text <bx id="1"/>bold text<ex id="1"/> more text.</source>
<target>普通文本 <bx id="1"/>粗体文本<ex id="1"/> 更多文本。</target>
</trans-unit>
</body>
</file>
</xliff>"""
    xliff_file = tmp_path / "inline_translation.xlf"
    xliff_file.write_text(content, encoding="utf-8")
    return xliff_file


# ── Parser tests ──────────────────────────────────────────────────────


class TestParser:
    """Tests for the xliff2html/parser.py module."""

    def test_parse_xliff_basic(self, sample_xliff: Path):
        """Parse a standard XLIFF and verify translations."""
        content = sample_xliff.read_text(encoding="utf-8")
        translations = parse_xliff(content)

        assert len(translations) == 4
        assert translations["heading1"] == "翻译标题"
        assert translations["para1"] == "翻译的段落内容。"
        assert translations["trans-unit-1"] == "占位符1"
        assert translations["trans-unit-2"] == "占位符2"

    def test_parse_xliff_empty(self):
        """Parse empty XLIFF content returns empty dict."""
        translations = parse_xliff("<xliff></xliff>")
        assert translations == {}

    def test_parse_xliff_no_target_fallback_to_source(self):
        """When <target> is missing, fall back to <source>."""
        content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2">
<file><body>
<trans-unit id="no-target">
<source>Source text only</source>
</trans-unit>
</body></file>
</xliff>"""
        translations = parse_xliff(content)
        assert translations["no-target"] == "Source text only"

    def test_strip_xliff_inline_tags(self):
        """Strip <bx/> and <ex/> tags from text."""
        text = "Hello <bx id=\"1\"/>world<ex id=\"1\"/>!"
        result = strip_xliff_inline_tags(text)
        assert result == "Hello world!"

    def test_strip_xliff_inline_tags_no_tags(self):
        """Text without inline tags is returned unchanged."""
        text = "Just plain text"
        result = strip_xliff_inline_tags(text)
        assert result == "Just plain text"


# ── Writer tests ──────────────────────────────────────────────────────


class TestWriter:
    """Tests for the xliff2html/writer.py module."""

    def test_parse_html_fragment(self):
        """Parse an HTML fragment into lxml elements."""
        fragment = "<strong>粗体</strong>"
        elements = parse_html_fragment(fragment)
        assert len(elements) == 1
        assert elements[0].tag == "strong"
        assert elements[0].text == "粗体"

    def test_wrap_translation_with_xliff_inline_no_tags(self):
        """When no inline tags, wrap returns None."""
        xliff_content = """<trans-unit id="simple">
<source>Hello</source>
<target>World</target>
</trans-unit>"""
        result = wrap_translation_with_xliff_inline(
            xliff_content, "simple", _INLINE_TRANSLATION_SENTINEL
        )
        assert result is None

    def test_wrap_translation_with_xliff_inline_with_tags(self):
        """When inline tags are present, generate synthetic fragment."""
        xliff_content = """<trans-unit id="fmt">
<source>Hello <bx id="1"/>world<ex id="1"/>!</source>
<target>Hola <bx id="1"/>mundo<ex id="1"/>!</target>
</trans-unit>"""
        result = wrap_translation_with_xliff_inline(
            xliff_content, "fmt", _INLINE_TRANSLATION_SENTINEL
        )
        assert result is not None
        assert _INLINE_TRANSLATION_SENTINEL in result

    def test_inject_translations_into_dom(self):
        """Inject translations via data-trans-unit-id attributes."""
        from lxml import html as lxml_html

        html_content = """<html><body>
<p data-trans-unit-id="p1">Original</p>
</body></html>"""
        root = lxml_html.fromstring(html_content)
        inject_translations_into_dom(
            root, {"p1": "Translated"}, frozenset({"img", "br"})
        )
        result = lxml_html.tostring(root, encoding="unicode", method="html")
        assert "Translated" in result
        assert "Original" not in result


# ── Full converter integration ────────────────────────────────────────


class TestConverterIntegration:
    """End-to-end tests for the XLIFF2HTMLConverter class."""

    def test_convert_basic(self, sample_html_template: Path, sample_xliff: Path, tmp_path: Path):
        """Convert XLIFF to HTML with basic translations."""
        output = tmp_path / "output.html"
        converter = XLIFF2HTMLConverter()

        result = converter.convert(
            sample_html_template, sample_xliff, output, ConverterOptions()
        )

        assert result.success, f"Conversion failed: {result.errors}"
        assert output.exists()

        content = output.read_text(encoding="utf-8")
        assert "翻译标题" in content
        assert "翻译的段落内容。" in content
        assert "占位符1" in content
        assert "占位符2" in content
        # Original text should be replaced
        assert "Original Heading" not in content

    def test_missing_html_template(self, sample_xliff: Path, tmp_path: Path):
        """Error when HTML template doesn't exist."""
        converter = XLIFF2HTMLConverter()
        output = tmp_path / "output.html"

        result = converter.convert(
            tmp_path / "nonexistent.html", sample_xliff, output, ConverterOptions()
        )

        assert not result.success
        assert "not found" in str(result.errors[0]).lower()

    def test_missing_xliff(self, sample_html_template: Path, tmp_path: Path):
        """Error when XLIFF file doesn't exist."""
        converter = XLIFF2HTMLConverter()
        output = tmp_path / "output.html"

        result = converter.convert(
            sample_html_template, tmp_path / "nonexistent.xlf", output, ConverterOptions()
        )

        assert not result.success
        assert "not found" in str(result.errors[0]).lower()

    def test_parse_xliff_integration(self, sample_xliff: Path):
        """Converter._parse_xliff still works via delegation."""
        converter = XLIFF2HTMLConverter()
        content = sample_xliff.read_text(encoding="utf-8")
        translations = converter._parse_xliff(content)
        assert len(translations) == 4

    def test_strip_inline_tags_integration(self):
        """Converter._strip_xliff_inline_tags still works."""
        converter = XLIFF2HTMLConverter()
        result = converter._strip_xliff_inline_tags("Hello <bx id=\"1\"/>world!")
        assert result == "Hello world!"


# ── Image injection tests ─────────────────────────────────────────────


class TestImages:
    """Tests for the xliff2html/images.py module."""

    def test_create_data_uri(self):
        """Create a data URI from bytes."""
        img_bytes = b"fake-image-bytes"
        uri = create_data_uri(img_bytes, "image/png")
        assert uri.startswith("data:image/png;base64,")
        assert uri == "data:image/png;base64,ZmFrZS1pbWFnZS1ieXRlcw=="

    def test_get_image_bytes_with_base64(self):
        """Get image bytes from base64 data."""
        import base64
        raw = b"test-image-data"
        b64 = base64.b64encode(raw).decode("utf-8")
        img = ImagePlacement(data_base64=b64, mime_type="image/png")
        result = get_image_bytes(img)
        assert result == raw

    def test_get_image_bytes_invalid(self):
        """Get image bytes from invalid placement raises ValueError."""
        img = ImagePlacement(mime_type="image/png")
        with pytest.raises(ValueError):
            get_image_bytes(img)
