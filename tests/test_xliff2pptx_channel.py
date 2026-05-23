"""XLIFF to PPTX channel tests."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import zipfile
import io

import pytest
from lxml import etree

from orf.channels.xliff2pptx import XLIFF2PPTXConverter
from orf.converters.base import ConversionResult


@pytest.fixture
def sample_pptx_skeleton(tmp_path: Path) -> Path:
    """Create a minimal mock PPTX skeleton file (ZIP archive)."""
    pptx_path = tmp_path / "skeleton.pptx"

    # Create a minimal PPTX structure
    with zipfile.ZipFile(pptx_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add [Content_Types].xml
        content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>"""
        zf.writestr("[Content_Types].xml", content_types)

        # Add minimal slide XML with text
        slide_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
    <p:cSld>
        <p:spTree>
            <p:sp>
                <p:txBody>
                    <a:p>
                        <a:r>
                            <a:t>Hello World</a:t>
                        </a:r>
                    </a:p>
                </p:txBody>
            </p:sp>
        </p:spTree>
    </p:cSld>
</p:sld>"""
        zf.writestr("ppt/slides/slide1.xml", slide_xml)

    return pptx_path


@pytest.fixture
def sample_xliff(tmp_path: Path) -> Path:
    """Create a minimal mock XLIFF file."""
    xliff_path = tmp_path / "translation.xlf"
    xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0">
    <file original="slide1" datatype="plaintext">
        <body>
            <trans-unit id="1">
                <source>Hello World</source>
                <target>你好 世界</target>
            </trans-unit>
        </body>
    </file>
</xliff>"""
    xliff_path.write_text(xliff_content, encoding="utf-8")
    return xliff_path


class TestXLIFF2PPTXConverter:
    """Test XLIFF to PPTX conversion."""

    def test_supported_format(self):
        """Test that supported_format returns PPTX."""
        converter = XLIFF2PPTXConverter()
        assert converter.supported_format == "PPTX"

    def test_validate_input_valid(self, sample_pptx_skeleton: Path):
        """Test validation with valid PPTX file."""
        converter = XLIFF2PPTXConverter()
        assert converter.validate_input(sample_pptx_skeleton) is True

    def test_validate_input_invalid_extension(self, tmp_path: Path):
        """Test validation with wrong file extension."""
        txt_file = tmp_path / "test.txt"
        txt_file.touch()

        converter = XLIFF2PPTXConverter()
        assert converter.validate_input(txt_file) is False

    def test_validate_input_not_exists(self):
        """Test validation with non-existent file."""
        converter = XLIFF2PPTXConverter()
        assert converter.validate_input("/nonexistent/file.pptx") is False

    def test_convert_success(self, sample_pptx_skeleton: Path, sample_xliff: Path, tmp_path: Path):
        """Test successful XLIFF to PPTX conversion."""
        output = tmp_path / "output.pptx"

        converter = XLIFF2PPTXConverter()
        result = converter.convert(sample_pptx_skeleton, sample_xliff, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert result.output_path == output
        assert output.exists()

    def test_convert_with_inline_formatting(self, sample_pptx_skeleton: Path, tmp_path: Path):
        """Test conversion with inline formatting in XLIFF."""
        # Create XLIFF with inline formatting markers
        xliff_path = tmp_path / "translation.xlf"
        xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0">
    <file original="slide1" datatype="plaintext">
        <body>
            <trans-unit id="1">
                <source>Hello World</source>
                <target><bpt id="1">&lt;b&gt;</bpt>你好<ept id="1">&lt;/b&gt;</ept> 世界</target>
            </trans-unit>
        </body>
    </file>
</xliff>"""
        xliff_path.write_text(xliff_content, encoding="utf-8")
        output = tmp_path / "output.pptx"

        converter = XLIFF2PPTXConverter()
        result = converter.convert(sample_pptx_skeleton, xliff_path, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert "units_translated" in result.metadata

    def test_convert_invalid_skeleton(self, sample_xliff: Path, tmp_path: Path):
        """Test conversion with invalid/missing PPTX skeleton."""
        invalid_skeleton = tmp_path / "nonexistent.pptx"
        output = tmp_path / "output.pptx"

        converter = XLIFF2PPTXConverter()
        result = converter.convert(invalid_skeleton, sample_xliff, output)

        assert result.success is False
        assert len(result.errors) > 0
        assert "Failed to load PPTX skeleton" in result.errors[0]

    def test_convert_invalid_xliff(self, sample_pptx_skeleton: Path, tmp_path: Path):
        """Test conversion with invalid/malformed XLIFF."""
        # Create an invalid XLIFF file
        invalid_xliff = tmp_path / "invalid.xlf"
        invalid_xliff.write_text("not valid xml at all", encoding="utf-8")
        output = tmp_path / "output.pptx"

        converter = XLIFF2PPTXConverter()
        result = converter.convert(sample_pptx_skeleton, invalid_xliff, output)

        assert result.success is False
        assert len(result.errors) > 0
        assert "Failed to parse XLIFF" in result.errors[0]

    def test_convert_empty_xliff(self, sample_pptx_skeleton: Path, tmp_path: Path):
        """Test conversion with XLIFF containing no trans-units."""
        empty_xliff = tmp_path / "empty.xlf"
        empty_xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0">
    <file original="slide1" datatype="plaintext">
        <body/>
    </file>
</xliff>"""
        empty_xliff.write_text(empty_xliff_content, encoding="utf-8")
        output = tmp_path / "output.pptx"

        converter = XLIFF2PPTXConverter()
        result = converter.convert(sample_pptx_skeleton, empty_xliff, output)

        # Should succeed with no units translated
        assert result.success is True
        assert result.metadata["units_translated"] == 0

    @patch("orf.channels.xliff2pptx.SkeletonLoader")
    def test_repack_pptx_error(self, mock_loader, sample_pptx_skeleton: Path, sample_xliff: Path, tmp_path: Path):
        """Test handling of PPTX repack errors."""
        output = tmp_path / "output.pptx"

        # Make repack raise an error
        with patch.object(XLIFF2PPTXConverter, "_repack_pptx", side_effect=IOError("Disk full")):
            converter = XLIFF2PPTXConverter()
            result = converter.convert(sample_pptx_skeleton, sample_xliff, output)

            assert result.success is False
            assert "Failed to repack PPTX" in result.errors[0]

    def test_load_pptx_skeleton(self, sample_pptx_skeleton: Path):
        """Test PPTX skeleton loading."""
        converter = XLIFF2PPTXConverter()
        result = converter._load_pptx_skeleton(sample_pptx_skeleton)

        assert "files" in result
        assert "bytes" in result
        assert len(result["files"]) > 0
        assert "ppt/slides/slide1.xml" in result["files"]

    def test_parse_xliff(self, sample_xliff: Path):
        """Test XLIFF parsing."""
        converter = XLIFF2PPTXConverter()
        result = converter._parse_xliff(sample_xliff)

        assert "units" in result
        assert len(result["units"]) == 1
        assert result["units"][0]["source"] == "Hello World"
        assert result["units"][0]["target"] == "你好 世界"

    def test_get_element_text(self):
        """Test element text extraction."""
        converter = XLIFF2PPTXConverter()

        # Create a simple element for testing
        xml = "<root><child>text<sub>sub content</sub>tail</child></root>"
        element = etree.fromstring(xml)

        # Test with None
        assert converter._get_element_text(None) == ""

        # Test with element having text and children
        child = element.find("child")
        assert converter._get_element_text(child) == "textsub contenttail"