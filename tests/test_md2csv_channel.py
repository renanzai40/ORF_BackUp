"""MD to CSV channel tests."""

from pathlib import Path

import pytest
from orf.converters.base import ConversionResult


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    content = """# Sample Document

| Name | Age | City |
|------|-----|------|
| Alice | 30 | Beijing |
| Bob | 25 | Shanghai |
    """
    md_file = tmp_path / "test.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


@pytest.fixture
def simple_table_md(tmp_path: Path) -> Path:
    content = """| col1 | col2 |
|------|-----|
| a    | b   |
| c    | d   |
"""
    md_file = tmp_path / "simple.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


@pytest.fixture
def empty_table_md(tmp_path: Path) -> Path:
    content = """| col1 | col2 |
|------|-----|
"""
    md_file = tmp_path / "empty.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


@pytest.fixture
def no_table_md(tmp_path: Path) -> Path:
    content = """# Just Text

No table here.
"""
    md_file = tmp_path / "note.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


class TestMD2CSVConverter:
    def test_supported_format(self):
        from orf.channels.md2csv import MD2CSVConverter

        converter = MD2CSVConverter()
        assert converter.supported_format == "CSV"

    def test_validate_input_valid_md(self, sample_md: Path):
        from orf.channels.md2csv import MD2CSVConverter

        converter = MD2CSVConverter()
        assert converter.validate_input(sample_md) is True

    def test_validate_input_invalid_extension(self, tmp_path: Path):
        from orf.channels.md2csv import MD2CSVConverter

        txt_file = tmp_path / "test.txt"
        txt_file.touch()

        converter = MD2CSVConverter()
        assert converter.validate_input(txt_file) is False

    def test_convert_simple_table(self, simple_table_md: Path, tmp_path: Path):
        from orf.channels.md2csv import MD2CSVConverter

        output = tmp_path / "output.csv"
        converter = MD2CSVConverter()
        result = converter.convert(simple_table_md, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "col1" in content
        assert "col2" in content
        assert "a" in content
        assert "b" in content

    def test_convert_preserves_header_row(self, simple_table_md: Path, tmp_path: Path):
        from orf.channels.md2csv import MD2CSVConverter

        output = tmp_path / "output.csv"
        converter = MD2CSVConverter()
        result = converter.convert(simple_table_md, output)

        lines = output.read_text(encoding="utf-8").strip().split("\n")
        assert "col1" in lines[0]
        assert "col2" in lines[0]

    def test_convert_delimiter_comma(self, simple_table_md: Path, tmp_path: Path):
        from orf.channels.md2csv import MD2CSVConverter

        output = tmp_path / "output.csv"
        converter = MD2CSVConverter()
        result = converter.convert(simple_table_md, output, delimiter=",")

        content = output.read_text(encoding="utf-8")
        assert "," in content
        assert ";" not in content

    def test_convert_delimiter_semicolon(self, simple_table_md: Path, tmp_path: Path):
        from orf.channels.md2csv import MD2CSVConverter

        output = tmp_path / "output.csv"
        converter = MD2CSVConverter()
        result = converter.convert(simple_table_md, output, delimiter=";")

        content = output.read_text(encoding="utf-8")
        assert ";" in content
        assert ",," not in content

    def test_convert_empty_table(self, empty_table_md: Path, tmp_path: Path):
        from orf.channels.md2csv import MD2CSVConverter

        output = tmp_path / "output.csv"
        converter = MD2CSVConverter()
        result = converter.convert(empty_table_md, output)

        assert result.success is True
        content = output.read_text(encoding="utf-8").strip()
        assert content == "" or content.count("\n") == 0

    def test_convert_non_table_md(self, no_table_md: Path, tmp_path: Path):
        from orf.channels.md2csv import MD2CSVConverter

        output = tmp_path / "output.csv"
        converter = MD2CSVConverter()
        result = converter.convert(no_table_md, output)

        assert result.success is True
        assert output.exists()

    def test_convert_success_result(self, sample_md: Path, tmp_path: Path):
        from orf.channels.md2csv import MD2CSVConverter

        output = tmp_path / "output.csv"
        converter = MD2CSVConverter()
        result = converter.convert(sample_md, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert result.output_path == output
        assert result.errors == []