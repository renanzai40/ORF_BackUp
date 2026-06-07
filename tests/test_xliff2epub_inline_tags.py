"""Regression tests for XLIFF inline tag handling in xliff2epub channel.

T3 of the ship-ready remediation plan v2: the previous regex-based
``_parse_xliff`` implementation captured inline markup as raw text
(``<g>``, ``<bx>``, ``<ex>``, ``<ph>``, ``<it>``) and could not handle
CDATA or multi-line ``<target>`` bodies correctly.

These tests pin the contract that ``_parse_xliff`` must:

* flatten inline tags via the XML tree, NOT carry markup into the
  returned segment text;
* preserve whitespace boundaries (newlines, spaces) so multi-line
  targets are still readable;
* read CDATA content as text, not as the literal ``[CDATA[`` marker;
* support both XLIFF 1.2 (``trans-unit``) and XLIFF 2.0
  (``unit``/``segment``) structures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from orf.channels.xliff2epub import XLIFF2EPUBConverter


# ---------------------------------------------------------------------------
# XLIFF 1.2 fixtures
# ---------------------------------------------------------------------------

XLIFF_12_PLAIN = """<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="x.html" source-language="en" target-language="zh">
    <body>
      <trans-unit id="unit-1">
        <source>Hello <g id="1">world</g>!</source>
        <target>Hello <g id="1">world</g>!</target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""


XLIFF_12_BX_EX = """<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="x.html" source-language="en" target-language="zh">
    <body>
      <trans-unit id="bold">
        <source>Text with <bx id="b1"/>bold<ex id="b1"/> formatting</source>
        <target>Text with <bx id="b1"/>bold<ex id="b1"/> formatting</target>
      </trans-unit>
      <trans-unit id="multi">
        <source>Line one
emphasized
line three</source>
        <target>Line one
<bx id="b1"/>emphasized<ex id="b1"/>
line three</target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""


XLIFF_12_CDATA = """<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="x.html" source-language="en" target-language="zh">
    <body>
      <trans-unit id="cdata-unit">
        <source>code sample</source>
        <target><![CDATA[if (a < b && b > c) { return true; }]]></target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""


# ---------------------------------------------------------------------------
# XLIFF 2.0 fixtures
# ---------------------------------------------------------------------------

XLIFF_20_G_TAG = """<?xml version="1.0" encoding="utf-8"?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0"
       srcLang="en" trgLang="zh">
  <file id="f1">
    <unit id="u-g">
      <segment>
        <target>Hello <g id="1">world</g>!</target>
      </segment>
    </unit>
  </file>
</xliff>
"""


XLIFF_20_PH_IT = """<?xml version="1.0" encoding="utf-8"?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0"
       srcLang="en" trgLang="zh">
  <file id="f1">
    <unit id="u-ph">
      <segment>
        <target>Press <ph id="1"/> to continue</target>
      </segment>
    </unit>
    <unit id="u-it">
      <segment>
        <target>See <it id="2" pos="open"/>link<it id="2" pos="close"/> for details</target>
      </segment>
    </unit>
  </file>
</xliff>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_xliff(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestXLIFF2EPUBParseInlineTags:
    """T3 contract: ``_parse_xliff`` must flatten inline XLIFF tags."""

    def test_xliff_12_g_tag_is_flattened_to_text(self, tmp_path: Path) -> None:
        """The headline RED case from the remediation plan.

        Pre-fix regex returns ``'Hello <g id="1">world</g>!'`` because
        the regex captures raw markup. Post-fix itertext must return
        the human-readable ``'Hello world!'``.
        """
        xliff_path = _write_xliff(tmp_path, "g.xlf", XLIFF_12_PLAIN)
        converter = XLIFF2EPUBConverter()

        segments = converter._parse_xliff(xliff_path)

        assert segments == {"unit-1": "Hello world!"}

    def test_xliff_12_g_tag_value_does_not_contain_markup(self, tmp_path: Path) -> None:
        """STRONG assertion: no inline-tag markup should leak into text."""
        xliff_path = _write_xliff(tmp_path, "g.xlf", XLIFF_12_PLAIN)
        converter = XLIFF2EPUBConverter()

        segments = converter._parse_xliff(xliff_path)

        value = segments["unit-1"]
        assert "<" not in value
        assert ">" not in value
        assert "&lt;" not in value
        assert "&gt;" not in value

    def test_xliff_12_bx_ex_tags_are_flattened(self, tmp_path: Path) -> None:
        """``<bx>`` / ``<ex>`` pair markers must vanish from segment text."""
        xliff_path = _write_xliff(tmp_path, "bx_ex.xlf", XLIFF_12_BX_EX)
        converter = XLIFF2EPUBConverter()

        segments = converter._parse_xliff(xliff_path)

        assert segments["bold"] == "Text with bold formatting"
        assert "<bx" not in segments["bold"]
        assert "<ex" not in segments["bold"]

    def test_xliff_12_multiline_target_preserves_newlines(self, tmp_path: Path) -> None:
        """Multi-line ``<target>`` must keep newlines and not capture markup."""
        xliff_path = _write_xliff(tmp_path, "multi.xlf", XLIFF_12_BX_EX)
        converter = XLIFF2EPUBConverter()

        segments = converter._parse_xliff(xliff_path)

        # 'Line one\nemphasized\nline three' — bx/ex removed, newlines kept
        assert segments["multi"] == "Line one\nemphasized\nline three"

    def test_xliff_12_cdata_content_is_unwrapped(self, tmp_path: Path) -> None:
        """CDATA-wrapped target text must be unwrapped, not copied verbatim.

        Pre-fix regex captures ``<![CDATA[...]]>`` literally; post-fix
        itertext gives the inner text without CDATA delimiters.
        """
        xliff_path = _write_xliff(tmp_path, "cdata.xlf", XLIFF_12_CDATA)
        converter = XLIFF2EPUBConverter()

        segments = converter._parse_xliff(xliff_path)

        assert segments["cdata-unit"] == "if (a < b && b > c) { return true; }"
        assert "[CDATA[" not in segments["cdata-unit"]
        assert "]]>" not in segments["cdata-unit"]

    def test_xliff_20_g_tag_is_flattened(self, tmp_path: Path) -> None:
        """XLIFF 2.0 ``<g>`` tags in ``unit/segment/target`` must flatten."""
        xliff_path = _write_xliff(tmp_path, "g20.xlf", XLIFF_20_G_TAG)
        converter = XLIFF2EPUBConverter()

        segments = converter._parse_xliff(xliff_path)

        assert segments == {"u-g": "Hello world!"}

    def test_xliff_20_ph_and_it_tags_are_flattened(self, tmp_path: Path) -> None:
        """XLIFF 2.0 ``<ph>`` (placeholder) and ``<it>`` (isolated) flatten.

        ``<it>`` carries ``pos="open"``/``pos="close"`` attributes which
        the regex never inspected; itertext handles them transparently.
        """
        xliff_path = _write_xliff(tmp_path, "ph_it.xlf", XLIFF_20_PH_IT)
        converter = XLIFF2EPUBConverter()

        segments = converter._parse_xliff(xliff_path)

        assert segments["u-ph"] == "Press  to continue"  # ph is self-closing
        assert segments["u-it"] == "See link for details"
