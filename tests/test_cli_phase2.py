"""Phase 2 CLI tests for ORF - apply-md auto-detect and new formats."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from orf.cli import main


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    """Create a minimal MD file for testing."""
    md_file = tmp_path / "test.md"
    md_file.write_text("---\nsource_lang: en\ntarget_lang: zh\n---\n\n# Test", encoding="utf-8")
    return md_file


class TestApplyMdAutoDetect:
    """Test apply-md auto-detect functionality."""

    def test_auto_detect_success(self, runner, sample_md, tmp_path):
        """Test --target-format auto successfully detects and converts."""
        output = tmp_path / "output.docx"

        with patch("orf.detection.FormatDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = "DOCX"
            mock_detector_class.return_value = mock_detector

            result = runner.invoke(
                main,
                [
                    "apply-md",
                    str(sample_md),
                    "--target-format",
                    "auto",
                    "--output",
                    str(output),
                ],
            )

            assert result.exit_code == 0
            mock_detector.detect.assert_called_once_with(sample_md)
            assert output.exists(), f"Output file not created: {output}"

    def test_auto_detect_not_found(self, runner, sample_md, tmp_path):
        """Test --target-format auto exits with error when detection fails."""
        from orf.error_handlers.conversion_error import FormatDetectionError

        output = tmp_path / "output.docx"

        with patch("orf.detection.FormatDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_detector.detect.side_effect = FormatDetectionError(
                str(sample_md), "Cannot detect format"
            )
            mock_detector_class.return_value = mock_detector

            result = runner.invoke(
                main,
                [
                    "apply-md",
                    str(sample_md),
                    "--target-format",
                    "auto",
                    "--output",
                    str(output),
                ],
            )

            assert result.exit_code == 1
            assert "Error" in result.output

    def test_apply_md_html_format(self, runner, sample_md, tmp_path):
        """Test --target-format html routes to MD2HTMLConverter."""
        output = tmp_path / "output.html"

        with patch("orf.channels.md2html.MD2HTMLConverter") as mock_converter_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output_path = output
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            mock_converter_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "apply-md",
                    str(sample_md),
                    "--target-format",
                    "html",
                    "--output",
                    str(output),
                ],
            )

            assert result.exit_code == 0
            assert "Created" in result.output
            mock_converter.convert.assert_called_once()

    def test_apply_md_rtf_format(self, runner, sample_md, tmp_path):
        """Test --target-format rtf routes to MD2RTFConverter."""
        output = tmp_path / "output.rtf"

        with patch("orf.channels.md2rtf.MD2RTFConverter") as mock_converter_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output_path = output
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            mock_converter_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "apply-md",
                    str(sample_md),
                    "--target-format",
                    "rtf",
                    "--output",
                    str(output),
                ],
            )

            assert result.exit_code == 0
            assert "Created" in result.output
            mock_converter.convert.assert_called_once()

    def test_apply_md_pdf_format(self, runner, sample_md, tmp_path):
        """Test --target-format pdf routes to MD2PDFConverter."""
        output = tmp_path / "output.pdf"

        with patch("orf.channels.md2pdf.MD2PDFConverter") as mock_converter_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output_path = output
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            mock_converter_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "apply-md",
                    str(sample_md),
                    "--target-format",
                    "pdf",
                    "--output",
                    str(output),
                ],
            )

            assert result.exit_code == 0
            assert "Created" in result.output
            mock_converter.convert.assert_called_once()

    def test_auto_detect_flag(self, runner, sample_md, tmp_path):
        """Test --auto-detect flag works."""
        output = tmp_path / "output.epub"

        with patch("orf.detection.FormatDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = "EPUB"
            mock_detector_class.return_value = mock_detector

            with patch("orf.channels.md2epub.MD2EPUBConverter") as mock_converter_class:
                mock_converter = MagicMock()
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.output_path = output
                mock_result.errors = []
                mock_converter.convert.return_value = mock_result
                mock_converter_class.return_value = mock_converter

                result = runner.invoke(
                    main,
                    [
                        "apply-md",
                        str(sample_md),
                        "--auto-detect",
                        "--output",
                        str(output),
                    ],
                )

                assert result.exit_code == 0
                mock_detector.detect.assert_called_once()

    def test_apply_md_docx_format(self, runner, sample_md, tmp_path):
        """Test --target-format docx routes to MD2DOCXConverter."""
        output = tmp_path / "output.docx"

        with patch("orf.channels.md2docx.MD2DOCXConverter") as mock_converter_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output_path = output
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            mock_converter_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "apply-md",
                    str(sample_md),
                    "--target-format",
                    "docx",
                    "--output",
                    str(output),
                ],
            )

            assert result.exit_code == 0
            assert "Created" in result.output
            mock_converter.convert.assert_called_once()

    def test_apply_md_odt_format(self, runner, sample_md, tmp_path):
        """Test --target-format odt routes to MD2ODTConverter."""
        output = tmp_path / "output.odt"

        with patch("orf.channels.md2odt.MD2ODTConverter") as mock_converter_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output_path = output
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            mock_converter_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "apply-md",
                    str(sample_md),
                    "--target-format",
                    "odt",
                    "--output",
                    str(output),
                ],
            )

            assert result.exit_code == 0
            assert "Created" in result.output
            mock_converter.convert.assert_called_once()

    def test_apply_md_epub_format(self, runner, sample_md, tmp_path):
        """Test --target-format epub routes to MD2EPUBConverter."""
        output = tmp_path / "output.epub"

        with patch("orf.channels.md2epub.MD2EPUBConverter") as mock_converter_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output_path = output
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            mock_converter_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "apply-md",
                    str(sample_md),
                    "--target-format",
                    "epub",
                    "--output",
                    str(output),
                ],
            )

            assert result.exit_code == 0
            assert "Created" in result.output
            mock_converter.convert.assert_called_once()

    def test_apply_md_invalid_input(self, runner, tmp_path):
        """Test apply-md handles non-existent file gracefully."""
        non_existent = tmp_path / "nonexistent.md"
        output = tmp_path / "output.docx"

        result = runner.invoke(
            main,
            [
                "apply-md",
                str(non_existent),
                "--target-format",
                "docx",
                "--output",
                str(output),
            ],
        )

        assert result.exit_code != 0
        assert "Error" in result.output or "nonexistent" in result.output

    def test_apply_md_conversion_failure(self, runner, sample_md, tmp_path):
        """Test apply-md handles converter failure properly."""
        output = tmp_path / "output.docx"

        with patch("orf.channels.md2docx.MD2DOCXConverter") as mock_converter_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = False
            mock_result.output_path = None
            mock_result.errors = ["Pandoc error: file not found"]
            mock_converter.convert.return_value = mock_result
            mock_converter_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "apply-md",
                    str(sample_md),
                    "--target-format",
                    "docx",
                    "--output",
                    str(output),
                ],
            )

            assert result.exit_code != 0
            assert "Conversion failed" in result.output

    def test_apply_md_unsupported_format(self, runner, sample_md, tmp_path):
        """Test apply-md rejects unsupported format."""
        output = tmp_path / "output.txt"

        result = runner.invoke(
            main,
            [
                "apply-md",
                str(sample_md),
                "--target-format",
                "txt",
                "--output",
                str(output),
            ],
        )

        assert result.exit_code != 0
        assert "Unsupported format" in result.output