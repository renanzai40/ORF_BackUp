"""MD to RTF channel tests."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from orf.channels.md2rtf import MD2RTFConverter
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


class TestMD2RTFConverter:
    def test_supported_format(self):
        converter = MD2RTFConverter()
        assert converter.supported_format == "RTF"

    def test_validate_input_valid(self, sample_md: Path):
        converter = MD2RTFConverter()
        assert converter.validate_input(sample_md) is True

    def test_validate_input_invalid(self, tmp_path: Path):
        txt_file = tmp_path / "test.txt"
        txt_file.touch()

        converter = MD2RTFConverter()
        assert converter.validate_input(txt_file) is False

    @patch("subprocess.run")
    def test_convert_success(self, mock_run, sample_md: Path, tmp_path: Path):
        output = tmp_path / "output.rtf"
        mock_run.return_value = MagicMock(
            returncode=0, stdout="", stderr=""
        )

        converter = MD2RTFConverter()
        result = converter.convert(sample_md, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert result.output_path == output

        call_args = mock_run.call_args[0][0]
        assert "pandoc" in call_args
        assert str(sample_md) in call_args
        assert str(output) in call_args
        assert "--to" in call_args
        assert "rtf" in call_args

    @patch("subprocess.run")
    def test_convert_pandoc_error(self, mock_run, sample_md: Path, tmp_path: Path):
        from subprocess import CalledProcessError

        output = tmp_path / "output.rtf"
        mock_run.side_effect = CalledProcessError(
            1, "pandoc", stderr="Unknown extension"
        )

        converter = MD2RTFConverter()
        result = converter.convert(sample_md, output)

        assert result.success is False
        assert len(result.errors) > 0
        assert "Pandoc error" in result.errors[0].message

    @patch("subprocess.run")
    def test_convert_pandoc_not_found(self, mock_run, sample_md: Path, tmp_path: Path):
        output = tmp_path / "output.rtf"
        mock_run.side_effect = FileNotFoundError()

        converter = MD2RTFConverter()
        result = converter.convert(sample_md, output)

        assert result.success is False
        assert "not in PATH" in result.errors[0].message

    def test_convert_invalid_input(self, tmp_path: Path):
        invalid_file = tmp_path / "nonexistent.md"
        output = tmp_path / "output.rtf"

        converter = MD2RTFConverter()
        result = converter.convert(invalid_file, output)

        assert result.success is False
        assert "Invalid input file" in result.errors[0].message