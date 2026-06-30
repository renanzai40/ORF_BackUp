"""MD to XLSX channel tests.

Tests for MD2XLSXConverter which extracts Markdown pipe tables into an
Excel workbook. ``openpyxl`` is required and is available in the test env.
"""

from pathlib import Path

import pytest
from openpyxl import load_workbook

from orf.channels.md2xlsx import MD2XLSXConverter
from orf.converters.base import ConversionResult


@pytest.fixture
def xlsx_simple_md(tmp_path: Path) -> Path:
    """MD with a small 2-column table with two data rows."""
    content = (
        "| a | b |\n"
        "|---|---|\n"
        "| 1 | 2 |\n"
        "| 3 | 4 |\n"
    )
    md = tmp_path / "table.md"
    md.write_text(content, encoding="utf-8")
    return md


@pytest.fixture
def xlsx_with_separators_md(tmp_path: Path) -> Path:
    """MD with multiple separator rows (e.g. alignment markers)."""
    content = (
        "| col1 | col2 | col3 |\n"
        "|:-----|:----:|-----:|\n"
        "| left | center | right |\n"
    )
    md = tmp_path / "seps.md"
    md.write_text(content, encoding="utf-8")
    return md


@pytest.fixture
def xlsx_empty_table_md(tmp_path: Path) -> Path:
    """MD with a header + separator but no data rows."""
    content = (
        "| col1 | col2 |\n"
        "|------|-----|\n"
    )
    md = tmp_path / "empty.md"
    md.write_text(content, encoding="utf-8")
    return md


@pytest.fixture
def xlsx_no_table_md(tmp_path: Path) -> Path:
    content = (
        "# Just a heading\n"
        "\n"
        "No pipes in sight.\n"
    )
    md = tmp_path / "notext.md"
    md.write_text(content, encoding="utf-8")
    return md


@pytest.fixture
def xlsx_whitespace_md(tmp_path: Path) -> Path:
    """Cells with surrounding whitespace — should be stripped."""
    content = (
        "|  a   |  b  |\n"
        "|------|-----|\n"
        "| data | more data |\n"
    )
    md = tmp_path / "ws.md"
    md.write_text(content, encoding="utf-8")
    return md


class TestMD2XLSXConverter:
    def test_supported_format(self):
        converter = MD2XLSXConverter()
        assert converter.supported_format == "XLSX"

    def test_validate_input_valid(self, xlsx_simple_md: Path):
        converter = MD2XLSXConverter()
        assert converter.validate_input(xlsx_simple_md) is True

    def test_validate_input_invalid_extension(self, tmp_path: Path):
        txt_file = tmp_path / "test.txt"
        txt_file.touch()

        converter = MD2XLSXConverter()
        assert converter.validate_input(txt_file) is False

    def test_validate_input_not_exists(self):
        converter = MD2XLSXConverter()
        assert converter.validate_input("/nonexistent/file.md") is False

    def test_convert_parses_table_with_headers_and_rows(
        self, xlsx_simple_md: Path, tmp_path: Path
    ):
        output = tmp_path / "out.xlsx"

        converter = MD2XLSXConverter()
        result = converter.convert(xlsx_simple_md, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert result.output_path == output
        assert output.exists()

        wb = load_workbook(output)
        ws = wb.active
        assert ws is not None
        rows = list(ws.iter_rows(values_only=True))
        assert rows[0] == ("a", "b")
        assert rows[1] == ("1", "2")
        assert rows[2] == ("3", "4")

    def test_convert_skips_separator_rows(
        self, xlsx_with_separators_md: Path, tmp_path: Path
    ):
        output = tmp_path / "seps.xlsx"

        converter = MD2XLSXConverter()
        result = converter.convert(xlsx_with_separators_md, output)

        assert result.success is True
        wb = load_workbook(output)
        ws = wb.active
        assert ws is not None
        rows = list(ws.iter_rows(values_only=True))
        # Header + 1 data row; the separator `|:---|:---:|...:|` is dropped.
        assert len(rows) == 2
        assert rows[0] == ("col1", "col2", "col3")
        assert rows[1] == ("left", "center", "right")

    def test_convert_empty_table_creates_empty_workbook(
        self, xlsx_empty_table_md: Path, tmp_path: Path
    ):
        output = tmp_path / "empty.xlsx"

        converter = MD2XLSXConverter()
        result = converter.convert(xlsx_empty_table_md, output)

        assert result.success is True
        assert output.exists()
        wb = load_workbook(output)
        ws = wb.active
        assert ws is not None
        rows = list(ws.iter_rows(values_only=True))
        # Header is the only row; no data rows appended.
        assert len(rows) == 1
        assert rows[0] == ("col1", "col2")
        assert result.metadata.get("rows") == 0

    def test_convert_uses_custom_sheet_name(
        self, xlsx_simple_md: Path, tmp_path: Path
    ):
        output = tmp_path / "named.xlsx"

        from orf.converters.options import ConverterOptions
        converter = MD2XLSXConverter()
        converter.convert(xlsx_simple_md, output, ConverterOptions(sheet_name="Data"))

        wb = load_workbook(output)
        assert "Data" in wb.sheetnames

    def test_convert_strips_cell_whitespace(
        self, xlsx_whitespace_md: Path, tmp_path: Path
    ):
        output = tmp_path / "ws.xlsx"

        converter = MD2XLSXConverter()
        result = converter.convert(xlsx_whitespace_md, output)

        assert result.success is True
        wb = load_workbook(output)
        ws = wb.active
        assert ws is not None
        rows = list(ws.iter_rows(values_only=True))
        assert rows[0] == ("a", "b")
        assert rows[1] == ("data", "more data")

    def test_convert_handles_no_table(
        self, xlsx_no_table_md: Path, tmp_path: Path
    ):
        output = tmp_path / "no_table.xlsx"

        converter = MD2XLSXConverter()
        result = converter.convert(xlsx_no_table_md, output)

        assert result.success is True
        assert output.exists()
        wb = load_workbook(output)
        ws = wb.active
        assert ws is not None
        rows = list(ws.iter_rows(values_only=True))
        assert rows == []  # empty workbook
        assert result.metadata.get("rows") == 0

    def test_inject_images_noop(self):
        converter = MD2XLSXConverter()
        images = [{"id": "img1"}]
        applied, remaining = converter.inject_images(
            skeleton_path="ignored",
            images=images,
            output_path="ignored",
        )
        assert applied == []
        assert remaining is images

    def test_convert_multi_table_creates_multiple_sheets(self, tmp_path: Path):
        """CI-G4: Two pipe-tables in one MD should produce >= 2 XLSX sheets."""
        content = (
            "# Multi-table document\n"
            "\n"
            "## Section A\n"
            "\n"
            "| h1 | h2 |\n"
            "|----|----|\n"
            "| a1  | a2 |\n"
            "\n"
            "## Section B\n"
            "\n"
            "| col1 | col2 | col3 |\n"
            "|------|------|------|\n"
            "| b1   | b2   | b3   |\n"
            "| b4   | b5   | b6   |\n"
        )
        md_file = tmp_path / "multi.md"
        md_file.write_text(content, encoding="utf-8")
        output = tmp_path / "multi.xlsx"

        converter = MD2XLSXConverter()
        result = converter.convert(md_file, output)

        assert result.success is True, f"convert failed: {result.errors}"
        assert output.exists()

        wb = load_workbook(output)
        assert len(wb.sheetnames) >= 2, (
            f"Expected >= 2 sheets for 2 distinct tables, got "
            f"{len(wb.sheetnames)}: {wb.sheetnames!r}"
        )
        sheet0_rows = list(wb[wb.sheetnames[0]].iter_rows(values_only=True))
        sheet1_rows = list(wb[wb.sheetnames[1]].iter_rows(values_only=True))
        assert len(sheet0_rows) == 2, f"sheet0 rows: {sheet0_rows!r}"
        assert len(sheet1_rows) == 3, f"sheet1 rows: {sheet1_rows!r}"
        assert ("h1", "h2") in sheet0_rows
        assert ("col1", "col2", "col3") in sheet1_rows
