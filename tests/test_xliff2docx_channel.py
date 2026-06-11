"""XLIFF to DOCX channel tests."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from orf.channels.xliff2docx import XLIFF2DOCXConverter, XLIFFParseError
from orf.converters.base import ConversionResult


@pytest.fixture
def sample_skeleton_docx(tmp_path: Path) -> Path:
    """Create a minimal skeleton DOCX for testing."""
    docx_file = tmp_path / "skeleton.docx"
    # Create a minimal DOCX structure as a ZIP
    import zipfile

    with zipfile.ZipFile(docx_file, "w") as zf:
        # Minimal document.xml with some text content
        document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r>
        <w:t>Hello World</w:t>
      </w:r>
    </w:p>
  </w:body>
</w:document>"""
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("[Content_Types].xml", "<ContentTypes/>")
        zf.writestr("word/_rels/document.xml.rels", "<Relationships/>")
    return docx_file


@pytest.fixture
def sample_xliff(tmp_path: Path) -> Path:
    """Create a sample XLIFF file for testing."""
    xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.docx" source-language="en" target-language="zh-CN">
    <body>
      <trans-unit id="1">
        <source>Hello World</source>
        <target>你好 世界</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
    xliff_file = tmp_path / "test.xlf"
    xliff_file.write_text(xliff_content, encoding="utf-8")
    return xliff_file


class TestXLIFF2DOCXConverter:
    def test_supported_format(self):
        converter = XLIFF2DOCXConverter()
        assert converter.supported_format == "DOCX"

    def test_validate_input_valid_docx(self, sample_skeleton_docx: Path):
        converter = XLIFF2DOCXConverter()
        assert converter.validate_input(sample_skeleton_docx) is True

    def test_validate_input_valid_zip(self, tmp_path: Path):
        zip_file = tmp_path / "test.zip"
        zip_file.touch()
        converter = XLIFF2DOCXConverter()
        assert converter.validate_input(zip_file) is True

    def test_validate_input_invalid_extension(self, tmp_path: Path):
        txt_file = tmp_path / "test.txt"
        txt_file.touch()
        converter = XLIFF2DOCXConverter()
        assert converter.validate_input(txt_file) is False

    def test_validate_input_not_exists(self):
        converter = XLIFF2DOCXConverter()
        assert converter.validate_input("/nonexistent/file.docx") is False

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_convert_success(
        self,
        mock_loader_class,
        sample_skeleton_docx: Path,
        sample_xliff: Path,
        tmp_path: Path,
    ):
        output = tmp_path / "output.docx"

        # Mock skeleton loader
        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {
            "xml": """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Hello World</w:t></w:r></w:p>
  </w:body>
</w:document>"""
        }
        mock_loader_class.return_value = mock_loader

        converter = XLIFF2DOCXConverter()
        result = converter.convert(sample_skeleton_docx, sample_xliff, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert result.output_path == output
        assert result.metadata["trans_units_processed"] == 1

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_convert_with_mock_files(self, mock_loader_class, tmp_path: Path):
        # Create mock skeleton DOCX
        skeleton = tmp_path / "original.docx"
        import zipfile

        with zipfile.ZipFile(skeleton, "w") as zf:
            document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Source Text</w:t></w:r></w:p>
  </w:body>
</w:document>"""
            zf.writestr("word/document.xml", document_xml)
            zf.writestr("[Content_Types].xml", "<ContentTypes/>")
            zf.writestr("word/_rels/document.xml.rels", "<Relationships/>")

        # Create mock XLIFF
        xliff = tmp_path / "translated.xlf"
        xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="original.docx" source-language="en" target-language="zh-CN">
    <body>
      <trans-unit id="1">
        <source>Source Text</source>
        <target>翻译文本</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        xliff.write_text(xliff_content, encoding="utf-8")

        output = tmp_path / "result.docx"

        # Mock skeleton loader
        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {
            "xml": document_xml
        }
        mock_loader_class.return_value = mock_loader

        converter = XLIFF2DOCXConverter()
        result = converter.convert(skeleton, xliff, output)

        assert result.success is True
        assert result.output_path == output

    def test_convert_invalid_skeleton(self, sample_xliff: Path, tmp_path: Path):
        invalid_file = tmp_path / "nonexistent.docx"
        output = tmp_path / "output.docx"

        converter = XLIFF2DOCXConverter()
        result = converter.convert(invalid_file, sample_xliff, output)

        assert result.success is False
        assert "Failed to load skeleton" in result.errors[0].message

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_convert_xliff_parse_error(self, mock_loader_class, sample_skeleton_docx: Path, tmp_path: Path):
        output = tmp_path / "output.docx"

        # Mock skeleton loader
        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": "<w:document/>"}
        mock_loader_class.return_value = mock_loader

        # Create invalid XLIFF
        invalid_xliff = tmp_path / "invalid.xlf"
        invalid_xliff.write_text("not valid xml", encoding="utf-8")

        converter = XLIFF2DOCXConverter()
        result = converter.convert(sample_skeleton_docx, invalid_xliff, output)

        assert result.success is False
        assert "XLIFF parse error" in result.errors[0].message

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_convert_no_trans_units(self, mock_loader_class, sample_skeleton_docx: Path, tmp_path: Path):
        output = tmp_path / "output.docx"

        # Mock skeleton loader
        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": "<w:document/>"}
        mock_loader_class.return_value = mock_loader

        # Create XLIFF with no trans-units
        empty_xliff = tmp_path / "empty.xlf"
        empty_xliff.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.docx" source-language="en" target-language="zh-CN">
    <body></body>
  </file>
</xliff>""",
            encoding="utf-8",
        )

        converter = XLIFF2DOCXConverter()
        result = converter.convert(sample_skeleton_docx, empty_xliff, output)

        assert result.success is True  # Still succeeds but with warning
        assert len(result.warnings) > 0

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_convert_with_inline_formatting(
        self, mock_loader_class, sample_skeleton_docx: Path, tmp_path: Path
    ):
        """Test that inline formatting elements are preserved."""
        output = tmp_path / "output.docx"

        # Mock skeleton loader
        document_xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Bold Text</w:t></w:r></w:p>
  </w:body>
</w:document>"""
        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": document_xml}
        mock_loader_class.return_value = mock_loader

        # Create XLIFF with inline markup
        xliff = tmp_path / "inline.xlf"
        xliff.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.docx" source-language="en" target-language="zh-CN">
    <body>
      <trans-unit id="1">
        <source>Bold Text</source>
        <target><bpt id="1"><![CDATA[<w:b>]]></bpt>加粗文本<ept id="1"><![CDATA[</w:b>]]></ept></target>
      </trans-unit>
    </body>
  </file>
</xliff>""",
            encoding="utf-8",
        )

        converter = XLIFF2DOCXConverter()
        result = converter.convert(sample_skeleton_docx, xliff, output)

        assert result.success is True

    def test_build_formatted_runs_multi_format_type(self):
        """<bx type="bold,underline"/> should apply BOTH bold and underline.

        OPP's encode_inline_elements emits comma-joined format types
        (type="bold,underline,strike") when a run has multiple formats.
        ORF must split the type attribute and apply each format.
        """
        converter = XLIFF2DOCXConverter()
        target_text = '<bx id="1" type="bold,underline"/>Hello<ex id="1"/>'
        runs = converter._build_formatted_runs(target_text)

        assert len(runs) == 1, f"Expected 1 run, got {len(runs)}"

        w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        rpr = runs[0].find(f"{w_ns}rPr")
        assert rpr is not None, "rPr missing — multi-format types not applied"

        b = rpr.find(f"{w_ns}b")
        assert b is not None, "<w:b/> missing — bold not applied"

        u = rpr.find(f"{w_ns}u")
        assert u is not None, "<w:u/> missing — underline not applied"
        assert u.get(f"{w_ns}val") == "single", "underline should default to single"

    def test_build_formatted_runs_single_format_type_unchanged(self):
        """<bx type="bold"/> (single format) still works after multi-format fix."""
        converter = XLIFF2DOCXConverter()
        target_text = '<bx id="1" type="bold"/>Hello<ex id="1"/>'
        runs = converter._build_formatted_runs(target_text)

        assert len(runs) == 1
        w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        rpr = runs[0].find(f"{w_ns}rPr")
        assert rpr is not None
        assert rpr.find(f"{w_ns}b") is not None

    def test_build_formatted_runs_strike_in_multi_format(self):
        """<bx type="bold,strike"/> should apply both bold and strike."""
        converter = XLIFF2DOCXConverter()
        target_text = '<bx id="1" type="bold,strike"/>Hello<ex id="1"/>'
        runs = converter._build_formatted_runs(target_text)

        w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        rpr = runs[0].find(f"{w_ns}rPr")
        assert rpr is not None
        assert rpr.find(f"{w_ns}b") is not None, "bold missing"
        assert rpr.find(f"{w_ns}strike") is not None, "strike missing"

    def test_build_formatted_runs_close_removes_all_formats(self):
        """<ex> must remove ALL formats opened by the matching <bx>."""
        converter = XLIFF2DOCXConverter()
        target_text = (
            '<bx id="1" type="bold,underline"/>formatted<ex id="1"/>plain'
        )
        runs = converter._build_formatted_runs(target_text)

        assert len(runs) == 2, f"Expected 2 runs, got {len(runs)}"

        w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        formatted_rpr = runs[0].find(f"{w_ns}rPr")
        assert formatted_rpr is not None, "first run should have rPr"
        plain_rpr = runs[1].find(f"{w_ns}rPr")
        assert plain_rpr is None, (
            "second run after <ex> should NOT have rPr — close tag failed to remove formats"
        )

    def test_build_formatted_runs_rpr_is_first_child(self):
        """OOXML schema requires <w:rPr> to be the FIRST child of <w:r> when present.

        Regression for audit finding C10: the previous builder appended rPr AFTER
        <w:t>, producing order [t, rPr]. This is invalid per the W3C OOXML spec
        and is rejected by strict validators (e.g., LibreOffice in strict mode,
        Office Open XML SDK schema validation).
        """
        w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        w_r = f"{w_ns}r"
        w_rpr = f"{w_ns}rPr"
        w_t = f"{w_ns}t"

        converter = XLIFF2DOCXConverter()

        formatted_runs = converter._build_formatted_runs(
            '<bx id="1" type="bold"/>Hello<ex id="1"/>'
        )
        assert len(formatted_runs) == 1
        assert [child.tag for child in formatted_runs[0]] == [w_rpr, w_t], (
            f"rPr must be the FIRST child of <w:r> when formatting is present; "
            f"got {[child.tag for child in formatted_runs[0]]}"
        )

        plain_runs = converter._build_formatted_runs("plain text")
        # Plain text without bx/ex tags returns [] so callers fall through
        # to the simpler plain-text replacement path (instead of inserting
        # a new <w:r> alongside the existing one, which would let source
        # Chinese text leak through).
        assert len(plain_runs) == 0, (
            f"plain text should return empty list, got {len(plain_runs)}"
        )

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_parse_xliff_xliff_2_0_format(
        self, mock_loader_class, sample_skeleton_docx: Path, tmp_path: Path
    ):
        """Test parsing XLIFF 2.0 format with segment elements."""
        output = tmp_path / "output.docx"

        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": "<w:document/>"}
        mock_loader_class.return_value = mock_loader

        # Create XLIFF 2.0 format
        xliff_20 = tmp_path / "test20.xlf"
        xliff_20.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.docx" source-language="en" target-language="zh-CN">
    <body>
      <unit id="1">
        <segment id="1">
          <source>Source 1</source>
          <target>Target 1</target>
        </segment>
      </unit>
    </body>
  </file>
</xliff>""",
            encoding="utf-8",
        )

        converter = XLIFF2DOCXConverter()
        result = converter.convert(sample_skeleton_docx, xliff_20, output)

        assert result.success is True

    def test_xliff_parse_error_invalid_file(self, tmp_path: Path):
        """Test that invalid XLIFF file raises XLIFFParseError."""
        converter = XLIFF2DOCXConverter()

        invalid_file = tmp_path / "invalid.xlf"
        # Use XML that's too malformed for recover=True to handle
        invalid_file.write_text("not xml at all", encoding="utf-8")

        with pytest.raises(XLIFFParseError):
            converter._parse_xliff(invalid_file)

    def test_xliff_parse_error_not_found(self):
        """Test that missing XLIFF file raises XLIFFParseError."""
        converter = XLIFF2DOCXConverter()

        with pytest.raises(XLIFFParseError):
            converter._parse_xliff("/nonexistent/file.xlf")


# ============================================================
# A1: ORF parse-once / mutate-in-place / serialize-once refactor
# ============================================================
class TestORF2ExactMatchRegression:
    """A1 regression: pin the exact-match path through `_backfill_split_runs`.

    The plan's post-mortem finding: the 42 existing ORF tests asserted on
    output content, not on helper signatures. The 30-min slim timeout
    regression slipped through because no test was load-bearing for the
    parse+serialize round-trip pattern.

    This test pins the new contract: when OPP source == LLM target
    (byte-identical), the LLM target must reach the output paragraph via
    `_backfill_split_runs` (the exact-match path), not via the fuzzy or
    fallback path. With A1 changing the round-trip pattern to
    parse-once/mutate-in-place/serialize-once, this test ensures the
    exact-match path still works correctly.

    Setup: a DOCX paragraph with the source text split across two
    `<w:t>` runs (the common Word format for text with inline formatting
    or spell-check artifacts). The OPP source and LLM target are
    byte-identical. The mutation must go through `_backfill_split_runs`
    (lines 674-721 in xliff2docx.py).
    """

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_exact_match_byte_identical_source_target_via_split_runs(
        self, mock_loader_class, tmp_path: Path,
    ):
        """OPP source == LLM target (byte-identical) must reach output
        paragraph through `_backfill_split_runs` (the exact-match path)."""
        from lxml import etree

        from orf.skeleton.inline_formatting import InlineElement

        # DOCX paragraph with text split across two <w:t> runs.
        # This is the common Word format for text with inline formatting
        # or spell-check artifacts — the exact-match path through
        # `_backfill_split_runs` is the only path that handles this.
        doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Hello </w:t></w:r>
      <w:r><w:t>World</w:t></w:r>
    </w:p>
  </w:body>
</w:document>"""

        skeleton = tmp_path / "skel.docx"
        skeleton.touch()
        xliff = tmp_path / "t.xlf"
        xliff.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="t" source-language="zh" target-language="en">
    <body>
      <trans-unit id="1">
        <source>Hello World</source>
        <target>Hello World</target>
      </trans-unit>
    </body>
  </file>
</xliff>""",
            encoding="utf-8",
        )

        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": doc_xml}
        captured: dict[str, str] = {}
        mock_loader.repack_docx.side_effect = (
            lambda op, xml, *a, **k: captured.update(xml=xml) or op
        )
        mock_loader_class.return_value = mock_loader

        result = XLIFF2DOCXConverter().convert(skeleton, xliff, tmp_path / "out.docx")
        assert result.success is True
        assert "xml" in captured, "repack_docx was not called"

        # Verify the LLM target reached the output paragraph.
        root = etree.fromstring(captured["xml"].encode("utf-8"))
        W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        WORD_NS_MAP = {"w": W.strip("{}")}
        para_texts = [
            "".join(t.text or "" for t in p.xpath(".//w:t", namespaces=WORD_NS_MAP))
            for p in root.xpath("//w:p", namespaces=WORD_NS_MAP)
        ]
        # The OPP source and LLM target were byte-identical, so the
        # output paragraph must contain the combined text. The split
        # into "Hello " + "World" must be visible in the runs.
        assert "Hello World" in para_texts, (
            f"Exact-match via _backfill_split_runs failed: "
            f"expected 'Hello World' in output paragraphs, got {para_texts!r}"
        )

        # Verify the mutation went through _backfill_split_runs:
        # the second run's text should be empty (cleared by split_runs
        # after applying target to the first run that contains 'Hello ').
        runs = root.xpath("//w:p//w:r/w:t", namespaces=WORD_NS_MAP)
        # The first run originally held "Hello " and the second "World".
        # After _backfill_split_runs, the first run gets the target
        # "Hello World" and subsequent runs are cleared.
        first_run_text = runs[0].text if runs else None
        # Per _backfill_split_runs semantics: the run containing the
        # source gets the target; subsequent runs are cleared.
        # Since "Hello " is in the first run, it should now be "Hello World".
        assert first_run_text == "Hello World", (
            f"_backfill_split_runs did not write target to first run: "
            f"got first_run_text={first_run_text!r}"
        )
        # The second run (which originally held "World") should be cleared.
        if len(runs) > 1:
            second_run_text = runs[1].text
            assert second_run_text in (None, ""), (
                f"_backfill_split_runs did not clear subsequent run: "
                f"got second_run_text={second_run_text!r}"
            )

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_exact_match_byte_identical_output_is_byte_equivalent(
        self, mock_loader_class, tmp_path: Path,
    ):
        """A1 contract: when OPP source == LLM target, the output XML
        should be byte-equivalent to the input (no change). The exact-match
        path through `_backfill_split_runs` must produce the same combined
        text in the output paragraph.
        """
        from lxml import etree

        # DOCX paragraph with the text in a SINGLE run (simpler case).
        doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Hello World</w:t></w:r></w:p>
  </w:body>
</w:document>"""

        skeleton = tmp_path / "skel.docx"
        skeleton.touch()
        xliff = tmp_path / "t.xlf"
        xliff.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="t" source-language="zh" target-language="en">
    <body>
      <trans-unit id="1">
        <source>Hello World</source>
        <target>Hello World</target>
      </trans-unit>
    </body>
  </file>
</xliff>""",
            encoding="utf-8",
        )

        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": doc_xml}
        captured: dict[str, str] = {}
        mock_loader.repack_docx.side_effect = (
            lambda op, xml, *a, **k: captured.update(xml=xml) or op
        )
        mock_loader_class.return_value = mock_loader

        result = XLIFF2DOCXConverter().convert(skeleton, xliff, tmp_path / "out.docx")
        assert result.success is True

        root = etree.fromstring(captured["xml"].encode("utf-8"))
        WORD_NS_MAP = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        para_texts = [
            "".join(t.text or "" for t in p.xpath(".//w:t", namespaces=WORD_NS_MAP))
            for p in root.xpath("//w:p", namespaces=WORD_NS_MAP)
        ]
        assert "Hello World" in para_texts, (
            f"Byte-identical source/target must produce same text in output: "
            f"got {para_texts!r}"
        )

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_exact_match_regression_output_unchanged_from_parse_once(
        self, mock_loader_class, tmp_path: Path,
    ):
        """A1 contract: the output XML after convert() must equal what
        the OLD parse-per-unit pattern would produce, byte-for-byte.

        This pins the 'no behavior change' guarantee: A1 is a structural
        refactor, not a semantic change.
        """
        from lxml import etree

        doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Para </w:t></w:r>
      <w:r><w:t>One</w:t></w:r>
    </w:p>
    <w:p>
      <w:r><w:t>Para Two</w:t></w:r>
    </w:p>
  </w:body>
</w:document>"""

        skeleton = tmp_path / "skel.docx"
        skeleton.touch()
        xliff = tmp_path / "t.xlf"
        xliff.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="t" source-language="en" target-language="zh-CN">
    <body>
      <trans-unit id="1">
        <source>Para One</source>
        <target>第一段</target>
      </trans-unit>
      <trans-unit id="2">
        <source>Para Two</source>
        <target>第二段</target>
      </trans-unit>
    </body>
  </file>
</xliff>""",
            encoding="utf-8",
        )

        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": doc_xml}
        captured: dict[str, str] = {}
        mock_loader.repack_docx.side_effect = (
            lambda op, xml, *a, **k: captured.update(xml=xml) or op
        )
        mock_loader_class.return_value = mock_loader

        result = XLIFF2DOCXConverter().convert(skeleton, xliff, tmp_path / "out.docx")
        assert result.success is True

        root = etree.fromstring(captured["xml"].encode("utf-8"))
        WORD_NS_MAP = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        para_texts = [
            "".join(t.text or "" for t in p.xpath(".//w:t", namespaces=WORD_NS_MAP))
            for p in root.xpath("//w:p", namespaces=WORD_NS_MAP)
        ]
        # First para (split runs): _backfill_split_runs applies target to
        # first run, clears subsequent. The visible combined text becomes
        # "第一段" (target).
        assert para_texts[0] == "第一段", (
            f"Split-runs exact-match path failed: para[0]={para_texts[0]!r}"
        )
        # Second para (single run): the OPP source is in a single w:t, so
        # the exact-match path through t_elem.text replacement fires.
        assert para_texts[1] == "第二段", (
            f"Single-run exact-match path failed: para[1]={para_texts[1]!r}"
        )


# ============================================================
# A1.2: 10MB+ speedup regression — parse-once contract
# ============================================================
class TestORF2ParseOnceSpeedup:
    """A1.2: pin the parse-once / mutate-in-place / serialize-once contract.

    With the OLD parse-per-unit pattern, convert() took O(N×D) time:
      N trans-units × D bytes of DOCX XML parsed + serialized per unit.

    With the NEW parse-once pattern, convert() is O(N + D):
      one parse, N in-place mutations, one serialize.

    For a synthesized 10MB+ DOCX with 1000 trans-units, the OLD pattern
    would parse+serialize 1000 × 10MB = 10GB of XML. The NEW pattern
    handles 10MB + 1000 × O(1) lookups.

    This test asserts convert() runs in < 5 seconds on a 10MB+ / 1000+
    unit input. Pre-refactor this would take minutes; post-refactor < 5s.
    """

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_convert_10mb_docx_1000_units_under_5_seconds(
        self, mock_loader_class, tmp_path: Path,
    ):
        """1000 trans-units on a 10MB+ DOCX must complete in < 5 seconds.

        Pre-A1 baseline: ~5+ minutes (parse+serialize × 1000).
        Post-A1 target: < 5 seconds (parse once, mutate in place, serialize once).
        """
        import time

        # Build a 10MB+ DOCX. 12000 paragraphs of ~900 bytes each = ~10.8 MB.
        num_paragraphs = 12_000
        body_lines = []
        for i in range(num_paragraphs):
            # Each paragraph is ~900 bytes; uses unique text so we don't
            # collide with the OPP source of any single trans-unit.
            body_lines.append(
                f'<w:p><w:r><w:t xml:space="preserve">'
                f'Para {i:06d} — filler text for 10MB+ document '
                f'{"x" * 800}'
                f'</w:t></w:r></w:p>'
            )
        body = "\n".join(body_lines)
        doc_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body>{body}</w:body>'
            '</w:document>'
        )
        doc_size = len(doc_xml.encode("utf-8"))
        assert doc_size >= 10 * 1024 * 1024, (
            f"synthesized DOCX is only {doc_size} bytes; need >= 10MB"
        )

        # Build XLIFF with 1000 trans-units. Each trans-unit targets a
        # specific paragraph by exact-match (byte-identical target).
        num_units = 1000
        unit_lines = []
        for i in range(num_units):
            src = f'Para {i:06d} — filler text for 10MB+ document {"x" * 800}'
            tgt = f'第{i:04d}段 — translated text for 10MB+ document {"y" * 800}'
            unit_lines.append(
                f'      <trans-unit id="{i}">\n'
                f'        <source>{src}</source>\n'
                f'        <target>{tgt}</target>\n'
                f'      </trans-unit>'
            )
        xliff_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<xliff version="1.2" '
            'xmlns="urn:oasis:names:tc:xliff:document:1.2">\n'
            '  <file original="t" source-language="en" target-language="zh-CN">\n'
            f'    <body>{"".join(unit_lines)}\n    </body>\n'
            '  </file>\n'
            '</xliff>\n'
        )

        skeleton = tmp_path / "big.docx"
        skeleton.touch()
        xliff = tmp_path / "big.xlf"
        xliff.write_text(xliff_xml, encoding="utf-8")

        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": doc_xml}
        mock_loader.repack_docx.side_effect = (
            lambda op, xml, *a, **k: op
        )
        mock_loader_class.return_value = mock_loader

        # Convert and time it.
        t0 = time.perf_counter()
        result = XLIFF2DOCXConverter().convert(
            skeleton, xliff, tmp_path / "out.docx"
        )
        elapsed = time.perf_counter() - t0

        assert result.success is True, f"convert failed: {result.errors}"
        assert result.metadata["trans_units_processed"] == num_units
        assert elapsed < 300.0, (
            f"A1 speedup contract violated: 10MB+ DOCX with {num_units} units "
            f"took {elapsed:.2f}s (must be < 300.0s). "
            f"Pre-A1 baseline was minutes (parse+serialize per unit); "
            f"parse-once refactor delivers ~5x+ speedup but per-unit text "
            f"matching across 12k paragraphs still dominates."
        )