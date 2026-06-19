"""MD to HTML channel tests."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from orf.channels.md2html import MD2HTMLConverter
from orf.converters.base import ConversionResult


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    content = """# 用户手册

 这是中文内容。

 ## 第一章

 - 列表项 1
 - 列表项 2

 | 表格 | 列 |
 |------|---|
 | 数据 | 值 |
 """
    md_file = tmp_path / "test.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


class TestMD2HTMLConverter:
    def test_supported_format(self):
        converter = MD2HTMLConverter()
        assert converter.supported_format == "HTML"

    def test_validate_input_valid(self, sample_md: Path):
        converter = MD2HTMLConverter()
        assert converter.validate_input(sample_md) is True

    def test_validate_input_invalid(self, tmp_path: Path):
        txt_file = tmp_path / "test.txt"
        txt_file.touch()

        converter = MD2HTMLConverter()
        assert converter.validate_input(txt_file) is False

    def test_convert_success(self, sample_md: Path, tmp_path: Path):
        output = tmp_path / "output.html"

        converter = MD2HTMLConverter()
        result = converter.convert(sample_md, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert result.output_path == output
        assert output.exists()
        assert output.stat().st_size > 0
        assert result.metadata["tool"] == "markdown"

    def test_convert_with_css(self, sample_md: Path, tmp_path: Path):
        output = tmp_path / "output.html"
        css_file = tmp_path / "style.css"
        css_file.write_text("body { color: red; }")

        converter = MD2HTMLConverter(css=css_file)
        result = converter.convert(sample_md, output)

        assert result.success is True
        content = output.read_text(encoding="utf-8")
        assert f'link rel="stylesheet" href="{css_file}"' in content

    @patch("orf.channels.md2html.markdown.Markdown")
    def test_convert_pandoc_error(self, mock_md_class, sample_md: Path, tmp_path: Path):
        output = tmp_path / "output.html"
        mock_instance = MagicMock()
        mock_instance.convert.side_effect = RuntimeError("Markdown parse failure")
        mock_md_class.return_value = mock_instance

        converter = MD2HTMLConverter()
        result = converter.convert(sample_md, output)

        assert result.success is False
        assert len(result.errors) > 0
        assert "HTML conversion error" in result.errors[0].message

    @patch("orf.channels.md2html.markdown.Markdown")
    def test_convert_pandoc_not_found(self, mock_md_class, sample_md: Path, tmp_path: Path):
        output = tmp_path / "output.html"
        mock_instance = MagicMock()
        mock_instance.convert.side_effect = OSError("Some I/O error")
        mock_md_class.return_value = mock_instance

        converter = MD2HTMLConverter()
        result = converter.convert(sample_md, output)

        assert result.success is False
        assert "HTML conversion error" in result.errors[0].message

    def test_convert_invalid_input(self, tmp_path: Path):
        invalid_file = tmp_path / "nonexistent.md"
        output = tmp_path / "output.html"

        converter = MD2HTMLConverter()
        result = converter.convert(invalid_file, output)

        assert result.success is False
        assert "Invalid input file" in result.errors[0].message

    def test_convert_pure_python_no_pandoc(self, tmp_path):
        """Test that the pure-Python markdown path works without pandoc."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Hello\n\nThis is a **test** paragraph.\n\n- List item 1\n- List item 2\n\n```python\nprint('hello')\n```")

        output_file = tmp_path / "output.html"
        converter = MD2HTMLConverter()
        result = converter.convert(str(md_file), str(output_file))

        assert result.success, f"Conversion failed: {result.errors}"
        assert output_file.exists(), "Output file not created"
        assert output_file.stat().st_size > 100, "Output too small"

        content = output_file.read_text(encoding='utf-8')
        assert '<!DOCTYPE html>' in content, "Missing DOCTYPE"
        assert '<h1' in content, "Missing h1 heading"
        assert '<strong>' in content, "Missing bold text"
        assert '<li>' in content, "Missing list item"
        assert '<code' in content, "Missing code block"