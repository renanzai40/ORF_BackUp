"""MD to ODT channel tests."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from orf.channels.md2odt import MD2ODTConverter
from orf.converters.base import ConversionResult


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    content = """# 用户手册

这是中文内容。
"""
    md_file = tmp_path / "test.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


class TestMD2ODTConverter:
    def test_supported_format(self):
        converter = MD2ODTConverter()
        assert converter.supported_format == "ODT"

    def test_validate_input_valid(self, sample_md: Path):
        converter = MD2ODTConverter()
        assert converter.validate_input(sample_md) is True

    def test_validate_input_invalid(self, tmp_path: Path):
        txt_file = tmp_path / "test.txt"
        txt_file.touch()
        converter = MD2ODTConverter()
        assert converter.validate_input(txt_file) is False

    @patch("subprocess.run")
    def test_convert_success(self, mock_run, sample_md: Path, tmp_path: Path):
        output = tmp_path / "output.odt"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        converter = MD2ODTConverter()
        result = converter.convert(sample_md, output)

        assert result.success is True
        assert result.output_path == output

        call_args = mock_run.call_args[0][0]
        assert "pandoc" in call_args
        assert "--to" in call_args
        assert "odt" in call_args

    @patch("subprocess.run")
    def test_convert_pandoc_error(self, mock_run, sample_md: Path, tmp_path: Path):
        from subprocess import CalledProcessError

        output = tmp_path / "output.odt"
        mock_run.side_effect = CalledProcessError(
            1, "pandoc", stderr="Unknown extension"
        )

        converter = MD2ODTConverter()
        result = converter.convert(sample_md, output)

        assert result.success is False
        assert len(result.errors) > 0