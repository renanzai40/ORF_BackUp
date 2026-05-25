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