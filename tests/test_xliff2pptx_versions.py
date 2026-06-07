"""T1: Multi-version XLIFF parsing for xliff2pptx converter.

Bug: xliff2pptx.py hardcodes XLIFF 2.0 namespace AND uses wrong element name
(trans-unit, which is the 1.x element name; 2.0 uses <unit>/<segment>).
This test ensures all three XLIFF versions (1.1, 1.2, 2.0) are correctly parsed.
"""

from pathlib import Path

import pytest

from orf.channels.xliff2pptx import XLIFF2PPTXConverter


# ---- Fixtures ---------------------------------------------------------------


@pytest.fixture
def xliff_1_1(tmp_path: Path) -> Path:
    """XLIFF 1.1 fixture with one trans-unit: Hello -> Bonjour."""
    xliff_path = tmp_path / "translation_1_1.xlf"
    content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.1" xmlns="urn:oasis:names:tc:xliff:document:1.1">
  <file original="slide1" source-language="en" target-language="fr" datatype="plaintext">
    <body>
      <trans-unit id="u1">
        <source>Hello</source>
        <target>Bonjour</target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""
    xliff_path.write_text(content, encoding="utf-8")
    return xliff_path


@pytest.fixture
def xliff_1_2(tmp_path: Path) -> Path:
    """XLIFF 1.2 fixture with one trans-unit: Hello -> Bonjour."""
    xliff_path = tmp_path / "translation_1_2.xlf"
    content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xsi:schemaLocation="urn:oasis:names:tc:xliff:document:1.2 xliff-core-1.2-transitional.xsd">
  <file original="slide1" source-language="en" target-language="fr" datatype="plaintext">
    <body>
      <trans-unit id="u1">
        <source>Hello</source>
        <target>Bonjour</target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""
    xliff_path.write_text(content, encoding="utf-8")
    return xliff_path


@pytest.fixture
def xliff_2_0(tmp_path: Path) -> Path:
    """XLIFF 2.0 fixture with one <unit>/<segment>: Hello -> Bonjour."""
    xliff_path = tmp_path / "translation_2_0.xlf"
    content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0"
       srcLang="en" trgLang="fr">
  <file id="f1" original="slide1">
    <unit id="u1">
      <segment id="s1">
        <source>Hello</source>
        <target>Bonjour</target>
      </segment>
    </unit>
  </file>
</xliff>
"""
    xliff_path.write_text(content, encoding="utf-8")
    return xliff_path


# ---- Tests ------------------------------------------------------------------


class TestXLIFFVersionsPPTX:
    """Each XLIFF version must be correctly parsed by xliff2pptx."""

    def test_xliff_1_1_parses_one_unit_with_bonjour(
        self, xliff_1_1: Path
    ) -> None:
        """XLIFF 1.1 fixture: 1 trans-unit parsed, target == 'Bonjour'."""
        converter = XLIFF2PPTXConverter()
        result = converter._parse_xliff(xliff_1_1)

        units = result["units"]
        assert len(units) == 1, (
            f"XLIFF 1.1: expected 1 unit, got {len(units)}: {units}"
        )
        assert units[0]["target"] == "Bonjour", (
            f"XLIFF 1.1: expected target 'Bonjour', got {units[0]['target']!r}"
        )

    def test_xliff_1_2_parses_one_unit_with_bonjour(
        self, xliff_1_2: Path
    ) -> None:
        """XLIFF 1.2 fixture: 1 trans-unit parsed, target == 'Bonjour'."""
        converter = XLIFF2PPTXConverter()
        result = converter._parse_xliff(xliff_1_2)

        units = result["units"]
        assert len(units) == 1, (
            f"XLIFF 1.2: expected 1 unit, got {len(units)}: {units}"
        )
        assert units[0]["target"] == "Bonjour", (
            f"XLIFF 1.2: expected target 'Bonjour', got {units[0]['target']!r}"
        )

    def test_xliff_2_0_parses_one_unit_with_bonjour(
        self, xliff_2_0: Path
    ) -> None:
        """XLIFF 2.0 fixture: 1 <unit>/<segment> parsed, target == 'Bonjour'."""
        converter = XLIFF2PPTXConverter()
        result = converter._parse_xliff(xliff_2_0)

        units = result["units"]
        assert len(units) == 1, (
            f"XLIFF 2.0: expected 1 unit, got {len(units)}: {units}"
        )
        assert units[0]["target"] == "Bonjour", (
            f"XLIFF 2.0: expected target 'Bonjour', got {units[0]['target']!r}"
        )
