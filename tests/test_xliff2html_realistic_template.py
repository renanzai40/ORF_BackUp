"""TDD regression test for xliff2html DOM injection.

The previous implementation replaced a literal ``[unit_id]`` substring with the
translated text. Real OPP-generated HTML templates instead mark translatable
nodes with the ``data-trans-unit-id="..."`` attribute, so the placeholder
string-replace silently no-op'd on real inputs.

The converter MUST locate the target node by the ``data-trans-unit-id``
attribute and replace the node's text content (preserving its tag and any
siblings) via an lxml-based DOM walk. This test asserts that contract with a
real xpath query on the parsed output.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree, html as lxml_html

from orf.channels.xliff2html import XLIFF2HTMLConverter
from orf.converters.options import ConverterOptions


# --- Fixtures --------------------------------------------------------------


REALISTIC_HTML = """<!DOCTYPE html>
<html>
<head><title>Test Document</title></head>
<body>
  <h1 data-trans-unit-id="unit-1">Original Heading</h1>
  <p data-trans-unit-id="unit-2">Original paragraph content.</p>
  <div class="footer">Footer text (not translatable)</div>
</body>
</html>
"""


REALISTIC_XLIFF = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
<file original="template.html" source-language="en" target-language="zh-CN">
<body>
  <trans-unit id="unit-1">
    <source>Original Heading</source>
    <target>翻译标题</target>
  </trans-unit>
  <trans-unit id="unit-2">
    <source>Original paragraph content.</source>
    <target>翻译的段落内容。</target>
  </trans-unit>
</body>
</file>
</xliff>
"""


@pytest.fixture
def realistic_template(tmp_path: Path) -> Path:
    path = tmp_path / "template.html"
    path.write_text(REALISTIC_HTML, encoding="utf-8")
    return path


@pytest.fixture
def realistic_xliff(tmp_path: Path) -> Path:
    path = tmp_path / "translation.xlf"
    path.write_text(REALISTIC_XLIFF, encoding="utf-8")
    return path


def _run_conversion(
    realistic_template: Path,
    realistic_xliff: Path,
    tmp_path: Path,
    *,
    preserve_inline: bool,
) -> Path:
    output = tmp_path / "output.html"
    converter = XLIFF2HTMLConverter()
    result = converter.convert(
        realistic_template,
        realistic_xliff,
        output,
        options=ConverterOptions(preserve_inline=preserve_inline),
    )
    assert result.success is True, f"conversion failed: {result.errors}"
    assert output.exists()
    return output


def _parse_html(path: Path):
    """Parse an HTML file as HTML, not as a strict XML document.

    ``etree.fromstring`` would put the root in the XHTML namespace and the
    DOCTYPE would trip the strict parser. Use the HTML parser so the test
    assertions match the way downstream tools (browsers, BeautifulSoup)
    will interpret the document.
    """
    return lxml_html.fromstring(path.read_text(encoding="utf-8"))


# --- Tests -----------------------------------------------------------------


class TestXLIFF2HTMLRealisticTemplate:
    """The OPP/real-world contract: tag the target with ``data-trans-unit-id``."""

    @pytest.mark.parametrize("preserve_inline", [True, False])
    def test_translation_lands_in_target_node(self, realistic_template, realistic_xliff, tmp_path, preserve_inline):
        output = _run_conversion(
            realistic_template,
            realistic_xliff,
            tmp_path,
            preserve_inline=preserve_inline,
        )

        tree = _parse_html(output)

        # Unit 1: <h1 data-trans-unit-id="unit-1"> should now hold the Chinese heading.
        h1 = tree.xpath('//h1[@data-trans-unit-id="unit-1"]')
        assert len(h1) == 1, f"expected exactly one <h1 data-trans-unit-id=unit-1>, got {len(h1)}"
        assert h1[0].text == "翻译标题"

        # Unit 2: <p data-trans-unit-id="unit-2"> should now hold the Chinese paragraph.
        p = tree.xpath('//p[@data-trans-unit-id="unit-2"]')
        assert len(p) == 1, f"expected exactly one <p data-trans-unit-id=unit-2>, got {len(p)}"
        assert p[0].text == "翻译的段落内容。"

    @pytest.mark.parametrize("preserve_inline", [True, False])
    def test_tag_and_siblings_are_preserved(self, realistic_template, realistic_xliff, tmp_path, preserve_inline):
        """The tag name and any non-text siblings must be preserved verbatim."""
        output = _run_conversion(
            realistic_template,
            realistic_xliff,
            tmp_path,
            preserve_inline=preserve_inline,
        )

        tree = _parse_html(output)

        # Tag name preserved.
        h1 = tree.xpath('//h1[@data-trans-unit-id="unit-1"]')[0]
        assert etree.QName(h1).localname == "h1"

        # The data-trans-unit-id attribute must remain (so subsequent passes are idempotent).
        assert h1.get("data-trans-unit-id") == "unit-1"
        p = tree.xpath('//p[@data-trans-unit-id="unit-2"]')[0]
        assert p.get("data-trans-unit-id") == "unit-2"

    @pytest.mark.parametrize("preserve_inline", [True, False])
    def test_unmarked_nodes_are_untouched(self, realistic_template, realistic_xliff, tmp_path, preserve_inline):
        """A node without ``data-trans-unit-id`` must not be modified."""
        output = _run_conversion(
            realistic_template,
            realistic_xliff,
            tmp_path,
            preserve_inline=preserve_inline,
        )

        tree = _parse_html(output)

        footer = tree.xpath('//div[@class="footer"]')[0]
        assert footer.text == "Footer text (not translatable)"

    def test_no_literal_bracket_placeholders_required(self, realistic_template, realistic_xliff, tmp_path):
        """Regression guard: the input contains NO ``[unit-1]`` / ``[unit-2]``
        markers. If the implementation falls back to string-replace, the output
        will still contain the original English text inside the marked tags.
        """
        output = _run_conversion(
            realistic_template,
            realistic_xliff,
            tmp_path,
            preserve_inline=False,
        )
        content = output.read_text(encoding="utf-8")

        # Literal placeholder markers must not appear in the output.
        assert "[unit-1]" not in content
        assert "[unit-2]" not in content

        # And the English originals must be gone from the marked nodes.
        tree = _parse_html(output)
        h1 = tree.xpath('//h1[@data-trans-unit-id="unit-1"]')[0]
        assert h1.text != "Original Heading"
        p = tree.xpath('//p[@data-trans-unit-id="unit-2"]')[0]
        assert p.text != "Original paragraph content."

    def test_preserve_inline_wraps_translation_with_html_tags(self, tmp_path):
        """When ``preserve_inline=True`` and the XLIFF carries ``<bx>`` /
        ``<ex>`` markers, the DOM injection must wrap the translation in the
        matching HTML formatting tag (``<strong>``, ``<em>``, etc.) — not
        leak the raw XLIFF tags, and not drop the formatting.
        """
        html = """<!DOCTYPE html>
<html><body>
  <p data-trans-unit-id="bold-1">Original bold text</p>
  <p data-trans-unit-id="plain-1">Original plain</p>
</body></html>
"""
        xliff = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2"><file><body>
  <trans-unit id="bold-1">
    <source>Original bold text</source>
    <target>原始<bx id="x1" type="bold"/>粗体<ex id="x1"/>文本</target>
  </trans-unit>
  <trans-unit id="plain-1">
    <source>Original plain</source>
    <target>普通文本</target>
  </trans-unit>
</body></file></xliff>
"""
        tmpl = tmp_path / "t.html"
        tmpl.write_text(html, encoding="utf-8")
        xlf = tmp_path / "t.xlf"
        xlf.write_text(xliff, encoding="utf-8")

        output = _run_conversion(tmpl, xlf, tmp_path, preserve_inline=True)

        tree = _parse_html(output)

        bold_p = tree.xpath('//p[@data-trans-unit-id="bold-1"]')[0]
        bold_html = lxml_html.tostring(bold_p, encoding="unicode", method="html")
        assert "<strong>" in bold_html
        assert "</strong>" in bold_html
        assert "<bx" not in bold_html
        assert "<ex" not in bold_html
        assert "粗体" in bold_html

        plain_p = tree.xpath('//p[@data-trans-unit-id="plain-1"]')[0]
        joined = "".join(plain_p.itertext())
        assert "普通文本" in joined
