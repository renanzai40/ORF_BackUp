"""XLIFF to ODF channel tests."""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from orf.channels.xliff2odf import XLIFF2ODFConverter, ODF_EXTENSIONS
from orf.converters.base import ConversionResult


@pytest.fixture
def sample_skeleton_odt(tmp_path: Path) -> Path:
    """Create a minimal skeleton ODT for testing."""
    odt_file = tmp_path / "skeleton.odt"
    # Create a minimal ODT structure as a ZIP
    import zipfile

    with zipfile.ZipFile(odt_file, "w") as zf:
        # Minimal content.xml with some text content
        content_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
                 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
  <office:body>
    <office:text>
      <text:p>Hello World</text:p>
    </office:text>
  </office:body>
</office:document>"""
        zf.writestr("content.xml", content_xml)
        zf.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        zf.writestr("[Content_Types].xml", "<ContentTypes/>")
    return odt_file


@pytest.fixture
def sample_xliff(tmp_path: Path) -> Path:
    """Create a sample XLIFF file for testing."""
    xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.odt" source-language="en" target-language="zh-CN">
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


class TestXLIFF2ODFConverter:
    def test_supported_format(self):
        converter = XLIFF2ODFConverter()
        assert converter.supported_format == "ODF"

    def test_validate_input_valid_odt(self, sample_skeleton_odt: Path):
        converter = XLIFF2ODFConverter()
        assert converter.validate_input(sample_skeleton_odt) is True

    def test_validate_input_valid_ods(self, tmp_path: Path):
        ods_file = tmp_path / "test.ods"
        ods_file.touch()
        converter = XLIFF2ODFConverter()
        assert converter.validate_input(ods_file) is True

    def test_validate_input_valid_odp(self, tmp_path: Path):
        odp_file = tmp_path / "test.odp"
        odp_file.touch()
        converter = XLIFF2ODFConverter()
        assert converter.validate_input(odp_file) is True

    def test_validate_input_invalid_extension(self, tmp_path: Path):
        doc_file = tmp_path / "test.docx"
        doc_file.touch()
        converter = XLIFF2ODFConverter()
        assert converter.validate_input(doc_file) is False

    def test_validate_input_not_exists(self):
        converter = XLIFF2ODFConverter()
        assert converter.validate_input("/nonexistent/file.odt") is False

    @patch("subprocess.run")
    def test_convert_success(
        self,
        mock_run,
        sample_skeleton_odt: Path,
        sample_xliff: Path,
        tmp_path: Path,
    ):
        output = tmp_path / "output.odt"

        # Mock successful subprocess execution
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Conversion completed",
            stderr="",
        )

        # Create output file to simulate xliff2odf behavior
        output.touch()

        converter = XLIFF2ODFConverter()
        result = converter.convert(sample_skeleton_odt, sample_xliff, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert result.output_path == output
        assert result.metadata["source_format"] == "XLIFF"
        assert result.metadata["target_format"] == "ODF"

    @patch("subprocess.run")
    def test_convert_with_mock_files(self, mock_run, tmp_path: Path):
        # Create mock skeleton ODT
        skeleton = tmp_path / "original.odt"
        import zipfile

        with zipfile.ZipFile(skeleton, "w") as zf:
            content_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
                 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
  <office:body>
    <office:text>
      <text:p>Source Text</text:p>
    </office:text>
  </office:body>
</office:document>"""
            zf.writestr("content.xml", content_xml)
            zf.writestr("mimetype", "application/vnd.oasis.opendocument.text")
            zf.writestr("[Content_Types].xml", "<ContentTypes/>")

        # Create mock XLIFF
        xliff = tmp_path / "translated.xlf"
        xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="original.odt" source-language="en" target-language="zh-CN">
    <body>
      <trans-unit id="1">
        <source>Source Text</source>
        <target>翻译文本</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        xliff.write_text(xliff_content, encoding="utf-8")

        output = tmp_path / "result.odt"

        # Mock successful subprocess execution
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Conversion completed",
            stderr="",
        )
        output.touch()

        converter = XLIFF2ODFConverter()
        result = converter.convert(skeleton, xliff, output)

        assert result.success is True
        assert result.output_path == output

    def test_convert_invalid_skeleton(self, sample_xliff: Path, tmp_path: Path):
        invalid_file = tmp_path / "nonexistent.odt"
        output = tmp_path / "output.odt"

        converter = XLIFF2ODFConverter()
        result = converter.convert(invalid_file, sample_xliff, output)

        assert result.success is False
        assert "Skeleton file not found" in result.errors[0].message

    def test_convert_invalid_xliff(self, sample_skeleton_odt: Path, tmp_path: Path):
        invalid_file = tmp_path / "nonexistent.xlf"
        output = tmp_path / "output.odt"

        converter = XLIFF2ODFConverter()
        result = converter.convert(sample_skeleton_odt, invalid_file, output)

        assert result.success is False
        assert "XLIFF file not found" in result.errors[0].message

    @patch("subprocess.run")
    def test_convert_subprocess_error(self, mock_run, sample_skeleton_odt: Path, sample_xliff: Path, tmp_path: Path):
        output = tmp_path / "output.odt"

        # Mock subprocess failure
        mock_run.side_effect = subprocess.CalledProcessError(1, "xliff2odf", "stderr output")

        converter = XLIFF2ODFConverter()
        result = converter.convert(sample_skeleton_odt, sample_xliff, output)

        assert result.success is False
        assert len(result.errors) > 0

    @patch("subprocess.run")
    def test_convert_command_not_found(self, mock_run, sample_skeleton_odt: Path, sample_xliff: Path, tmp_path: Path):
        output = tmp_path / "output.odt"

        # Mock FileNotFoundError for xliff2odf command
        mock_run.side_effect = FileNotFoundError("xliff2odf not found")

        converter = XLIFF2ODFConverter()
        result = converter.convert(sample_skeleton_odt, sample_xliff, output)

        assert result.success is False
        assert "xliff2odf command not found" in result.errors[0].message

    @patch("subprocess.run")
    def test_convert_with_exclude_patterns(self, mock_run, sample_skeleton_odt: Path, sample_xliff: Path, tmp_path: Path):
        output = tmp_path / "output.odt"

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Conversion completed",
            stderr="",
        )
        output.touch()

        converter = XLIFF2ODFConverter()
        result = converter.convert(
            sample_skeleton_odt, sample_xliff, output,
            exclude=["*.xml"]
        )

        assert result.success is True
        # Verify the command was called with exclude flag
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "-x" in cmd

    @patch("subprocess.run")
    def test_convert_with_timestamp_skip(self, mock_run, sample_skeleton_odt: Path, sample_xliff: Path, tmp_path: Path):
        output = tmp_path / "output.odt"

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Conversion completed",
            stderr="",
        )
        output.touch()

        converter = XLIFF2ODFConverter()
        result = converter.convert(
            sample_skeleton_odt, sample_xliff, output,
            timestamp=True
        )

        assert result.success is True
        # Verify the command was called with -S flag
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "-S" in cmd

    @patch("subprocess.run")
    def test_convert_output_not_created(self, mock_run, sample_skeleton_odt: Path, sample_xliff: Path, tmp_path: Path):
        output = tmp_path / "output.odt"

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Conversion completed",
            stderr="",
        )
        # Don't create output file - simulate xliff2odf failure

        converter = XLIFF2ODFConverter()
        result = converter.convert(sample_skeleton_odt, sample_xliff, output)

        assert result.success is False
        assert "output file was not created" in result.errors[0].message

    @patch("subprocess.run")
    def test_convert_with_multiple_exclude_patterns(self, mock_run, sample_skeleton_odt: Path, sample_xliff: Path, tmp_path: Path):
        output = tmp_path / "output.odt"

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Conversion completed",
            stderr="",
        )
        output.touch()

        converter = XLIFF2ODFConverter()
        result = converter.convert(
            sample_skeleton_odt, sample_xliff, output,
            exclude=["*.xml", "*.rdf"]
        )

        assert result.success is True
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        # Should have -x for each exclude pattern
        assert cmd.count("-x") == 2

    def test_odf_extensions(self):
        """Test that ODF_EXTENSIONS contains expected formats."""
        expected_extensions = {".odt", ".ods", ".odg", ".odi", ".odm", ".odp", ".otp", ".ots", ".ott"}
        assert ODF_EXTENSIONS == expected_extensions