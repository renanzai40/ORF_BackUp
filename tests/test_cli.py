"""CLI tests for ORF."""

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
def sample_docx(tmp_path: Path) -> Path:
    """Create a minimal DOCX file for testing."""
    import zipfile

    docx_file = tmp_path / "test.docx"
    with zipfile.ZipFile(docx_file, "w") as zf:
        document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Hello World</w:t></w:r></w:p>
  </w:body>
</w:document>"""
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("[Content_Types].xml", "<ContentTypes/>")
        zf.writestr("word/_rels/document.xml.rels", "<Relationships/>")
    return docx_file


@pytest.fixture
def sample_pptx(tmp_path: Path) -> Path:
    """Create a minimal PPTX file for testing."""
    import zipfile

    pptx_file = tmp_path / "test.pptx"
    with zipfile.ZipFile(pptx_file, "w") as zf:
        slide_xml = """<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:sp><p:txBody><p:p><p:r><p:t>Hello</p:t></p:r></p:p></p:txBody></p:sp></p:spTree></p:cSld>
</p:sld>"""
        zf.writestr("ppt/slides/slide1.xml", slide_xml)
        zf.writestr("[Content_Types].xml", "<ContentTypes/>")
    return pptx_file


@pytest.fixture
def sample_epub(tmp_path: Path) -> Path:
    """Create a minimal EPUB file for testing."""
    import zipfile

    epub_file = tmp_path / "test.epub"
    with zipfile.ZipFile(epub_file, "w") as zf:
        container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/content.opf", "<package version='2.0'/>")
        zf.writestr("OEBPS/chapter1.xhtml", "<html><body><p>Hello</p></body></html>")
    return epub_file


@pytest.fixture
def sample_html(tmp_path: Path) -> Path:
    """Create a minimal HTML file for testing."""
    html_file = tmp_path / "test.html"
    html_file.write_text("<html><body><p>Hello World</p></body></html>", encoding="utf-8")
    return html_file


@pytest.fixture
def sample_odt(tmp_path: Path) -> Path:
    """Create a minimal ODT file for testing."""
    import zipfile

    odt_file = tmp_path / "test.odt"
    with zipfile.ZipFile(odt_file, "w") as zf:
        content_xml = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:content">
  <office:body><office:text><text:p>Hello</text:p></office:text></office:body>
</office:document-content>"""
        zf.writestr("content.xml", content_xml)
        zf.writestr("[Content_Types].xml", "<ContentTypes/>")
    return odt_file


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


class TestCLI:
    """Test CLI commands."""

    def test_apply_xliff_docx(self, runner, sample_docx, sample_xliff, tmp_path):
        """Test apply-xliff command with DOCX format."""
        output = tmp_path / "output.docx"

        with patch("orf.channels.xliff2docx.XLIFF2DOCXConverter") as mock_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output_path = output
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            mock_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "apply-xliff",
                    str(sample_docx),
                    "--xliff",
                    str(sample_xliff),
                    "--output",
                    str(output),
                    "--format",
                    "docx",
                ],
            )

            assert result.exit_code == 0
            assert "Created" in result.output
            mock_converter.convert.assert_called_once()

    def test_apply_xliff_pptx(self, runner, sample_pptx, sample_xliff, tmp_path):
        """Test apply-xliff command with PPTX format."""
        output = tmp_path / "output.pptx"

        with patch("orf.channels.xliff2pptx.XLIFF2PPTXConverter") as mock_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output_path = output
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            mock_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "apply-xliff",
                    str(sample_pptx),
                    "--xliff",
                    str(sample_xliff),
                    "--output",
                    str(output),
                    "--format",
                    "pptx",
                ],
            )

            assert result.exit_code == 0
            assert "Created" in result.output
            mock_converter.convert.assert_called_once()

    def test_apply_xliff_epub(self, runner, sample_epub, sample_xliff, tmp_path):
        """Test apply-xliff command with EPUB format."""
        output = tmp_path / "output.epub"

        with patch("orf.channels.xliff2epub.XLIFF2EPUBConverter") as mock_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output_path = output
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            mock_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "apply-xliff",
                    str(sample_epub),
                    "--xliff",
                    str(sample_xliff),
                    "--output",
                    str(output),
                    "--format",
                    "epub",
                ],
            )

            assert result.exit_code == 0
            assert "Created" in result.output
            mock_converter.convert.assert_called_once()

    def test_apply_xliff_html(self, runner, sample_html, sample_xliff, tmp_path):
        """Test apply-xliff command with HTML format."""
        output = tmp_path / "output.html"

        with patch("orf.channels.xliff2html.XLIFF2HTMLConverter") as mock_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output_path = output
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            mock_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "apply-xliff",
                    str(sample_html),
                    "--xliff",
                    str(sample_xliff),
                    "--output",
                    str(output),
                    "--format",
                    "html",
                ],
            )

            assert result.exit_code == 0
            assert "Created" in result.output
            mock_converter.convert.assert_called_once()

    def test_apply_xliff_odt(self, runner, sample_odt, sample_xliff, tmp_path):
        """Test apply-xliff command with ODT format."""
        output = tmp_path / "output.odt"

        with patch("orf.channels.xliff2odf.XLIFF2ODFConverter") as mock_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output_path = output
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            mock_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "apply-xliff",
                    str(sample_odt),
                    "--xliff",
                    str(sample_xliff),
                    "--output",
                    str(output),
                    "--format",
                    "odt",
                ],
            )

            assert result.exit_code == 0
            assert "Created" in result.output
            mock_converter.convert.assert_called_once()

    def test_apply_xliff_failure(self, runner, sample_docx, sample_xliff, tmp_path):
        """Test apply-xliff command handles conversion failure."""
        output = tmp_path / "output.docx"

        with patch("orf.channels.xliff2docx.XLIFF2DOCXConverter") as mock_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = False
            mock_result.output_path = None
            mock_result.errors = ["Conversion failed: some error"]
            mock_converter.convert.return_value = mock_result
            mock_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "apply-xliff",
                    str(sample_docx),
                    "--xliff",
                    str(sample_xliff),
                    "--output",
                    str(output),
                    "--format",
                    "docx",
                ],
            )

        assert result.exit_code != 0


class TestConvertBatch:
    """Test convert-batch command."""

    def test_convert_batch_docx(self, runner, tmp_path):
        """Test batch convert to DOCX format."""
        # Create sample MD files with frontmatter
        md1 = tmp_path / "test1.md"
        md1.write_text("---\nsource_lang: en\ntarget_lang: zh\n---\n\n# Test1", encoding="utf-8")
        md2 = tmp_path / "test2.md"
        md2.write_text("---\nsource_lang: en\ntarget_lang: ja\n---\n\n# Test2", encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch("orf.channels.md2docx.MD2DOCXConverter") as mock_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output_path = output_dir / "test1.docx"
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            mock_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "convert-batch",
                    str(tmp_path),
                    "--target-format",
                    "docx",
                    "--output-dir",
                    str(output_dir),
                ],
            )

            assert result.exit_code == 0
            assert "succeeded" in result.output

    def test_convert_batch_odt(self, runner, tmp_path):
        """Test batch convert to ODT format."""
        md1 = tmp_path / "test1.md"
        md1.write_text("---\nsource_lang: en\ntarget_lang: zh\n---\n\n# Test1", encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch("orf.channels.md2odt.MD2ODTConverter") as mock_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output_path = output_dir / "test1.odt"
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            mock_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "convert-batch",
                    str(tmp_path),
                    "--target-format",
                    "odt",
                    "--output-dir",
                    str(output_dir),
                ],
            )

            assert result.exit_code == 0
            assert "succeeded" in result.output

    def test_convert_batch_epub(self, runner, tmp_path):
        """Test batch convert to EPUB format."""
        md1 = tmp_path / "test1.md"
        md1.write_text("---\nsource_lang: en\ntarget_lang: zh\n---\n\n# Test1", encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch("orf.channels.md2epub.MD2EPUBConverter") as mock_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output_path = output_dir / "test1.epub"
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            mock_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "convert-batch",
                    str(tmp_path),
                    "--target-format",
                    "epub",
                    "--output-dir",
                    str(output_dir),
                ],
            )

            assert result.exit_code == 0
            assert "succeeded" in result.output

    def test_convert_batch_no_files(self, runner, tmp_path):
        """Test convert-batch when no MD files found."""
        # Create a non-MD file
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Not a MD file", encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = runner.invoke(
            main,
            [
                "convert-batch",
                str(tmp_path),
                "--target-format",
                "docx",
                "--output-dir",
                str(output_dir),
            ],
        )

        assert result.exit_code == 0
        assert "No files found" in result.output

    def test_convert_batch_with_pattern(self, runner, tmp_path):
        """Test convert-batch with custom --pattern option."""
        md1 = tmp_path / "test1.md"
        md1.write_text("---\nsource_lang: en\ntarget_lang: zh\n---\n\n# Test1", encoding="utf-8")
        md2 = tmp_path / "test2.md"
        md2.write_text("---\nsource_lang: en\ntarget_lang: ja\n---\n\n# Test2", encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch("orf.channels.md2docx.MD2DOCXConverter") as mock_class:
            mock_converter = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.output_path = output_dir / "test1.docx"
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            mock_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "convert-batch",
                    str(tmp_path),
                    "--target-format",
                    "docx",
                    "--output-dir",
                    str(output_dir),
                    "--pattern",
                    "test1.md",
                ],
            )

            assert result.exit_code == 0

    def test_convert_batch_partial_failure(self, runner, tmp_path):
        """Test convert-batch partial success/failure handling."""
        md1 = tmp_path / "test1.md"
        md1.write_text("---\nsource_lang: en\ntarget_lang: zh\n---\n\n# Test1", encoding="utf-8")
        md2 = tmp_path / "test2.md"
        md2.write_text("---\nsource_lang: en\ntarget_lang: ja\n---\n\n# Test2", encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch("orf.channels.md2docx.MD2DOCXConverter") as mock_class:
            mock_converter = MagicMock()
            # First succeeds, second fails
            mock_converter.convert.side_effect = [
                MagicMock(success=True, output_path=output_dir / "test1.docx", errors=[]),
                MagicMock(success=False, output_path=None, errors=["Pandoc error"]),
            ]
            mock_class.return_value = mock_converter

            result = runner.invoke(
                main,
                [
                    "convert-batch",
                    str(tmp_path),
                    "--target-format",
                    "docx",
                    "--output-dir",
                    str(output_dir),
                ],
            )

            assert result.exit_code == 0
            assert "failed" in result.output
            assert "Conversion failed" in result.output

    def test_apply_xliff_missing_input(self, runner, tmp_path):
        """Test apply-xliff command fails gracefully with missing input."""
        xliff = tmp_path / "missing.xlf"
        output = tmp_path / "output.docx"

        result = runner.invoke(
            main,
            [
                "apply-xliff",
                str(xliff),  # input file that doesn't exist
                "--xliff",
                str(xliff),
                "--output",
                str(output),
                "--format",
                "docx",
            ],
        )

        assert result.exit_code != 0

    def test_apply_xliff_unsupported_format(self, runner, sample_docx, sample_xliff, tmp_path):
        """Test apply-xliff command rejects unsupported format."""
        output = tmp_path / "output.txt"

        result = runner.invoke(
            main,
            [
                "apply-xliff",
                str(sample_docx),
                "--xliff",
                str(sample_xliff),
                "--output",
                str(output),
                "--format",
                "txt",
            ],
        )

        assert result.exit_code != 0