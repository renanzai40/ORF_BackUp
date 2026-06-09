"""Tests for the DataSpecialist agent.

Covers:
- supported_formats
- happy paths for xlsx / csv / json
- UNSUPPORTED_FORMAT for unknown formats
- ImportError → MISSING_DEPENDENCY (mocked via constructor raising)
- Generic Exception → CONVERSION_ERROR
- output_path defaulting behavior
- BaseSpecialist hooks (can_handle, category, get_capabilities)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orf.agents.specialists.data_specialist import DataSpecialist
from orf.converters.base import ConversionResult


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    md = tmp_path / "in.md"
    md.write_text("| col1 | col2 |\n|------|------|\n| a | b |\n", encoding="utf-8")
    return md


@pytest.fixture
def specialist() -> DataSpecialist:
    return DataSpecialist()


def _ok(output: Path) -> ConversionResult:
    return ConversionResult(output_path=output, success=True)


# =============================================================================
# supported_formats / interface
# =============================================================================


class TestDataSpecialistInterface:
    def test_supported_formats(self, specialist: DataSpecialist):
        assert specialist.supported_formats == ["xlsx", "csv", "json"]

    @pytest.mark.parametrize("fmt", ["xlsx", "csv", "json"])
    def test_can_handle_supported(self, specialist: DataSpecialist, fmt: str):
        assert specialist.can_handle(fmt) is True

    def test_can_handle_unsupported(self, specialist: DataSpecialist):
        assert specialist.can_handle("docx") is False
        assert specialist.can_handle("html") is False

    def test_category(self, specialist: DataSpecialist):
        assert specialist.category == "data"

    def test_get_capabilities(self, specialist: DataSpecialist):
        caps = specialist.get_capabilities()
        assert caps["category"] == "data"
        assert caps["formats"] == ["xlsx", "csv", "json"]
        assert caps["supports_batch"] is True


# =============================================================================
# convert — happy paths
# =============================================================================


class TestDataSpecialistConvertHappy:
    def test_convert_xlsx(self, specialist: DataSpecialist, sample_md: Path, tmp_path: Path):
        out = tmp_path / "out.xlsx"
        with patch("orf.agents.specialists.data_specialist.MD2XLSXConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            result = specialist.convert(sample_md, out, "xlsx")

        assert result.success is True
        assert result.output_path == out
        instance.convert.assert_called_once()

    def test_convert_csv(self, specialist: DataSpecialist, sample_md: Path, tmp_path: Path):
        out = tmp_path / "out.csv"
        with patch("orf.agents.specialists.data_specialist.MD2CSVConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            result = specialist.convert(sample_md, out, "csv")

        assert result.success is True
        assert result.output_path == out

    def test_convert_json(self, specialist: DataSpecialist, sample_md: Path, tmp_path: Path):
        out = tmp_path / "out.json"
        with patch("orf.agents.specialists.data_specialist.MD2JSONConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            result = specialist.convert(sample_md, out, "json")

        assert result.success is True
        assert result.output_path == out


# =============================================================================
# convert — error paths
# =============================================================================


class TestDataSpecialistConvertErrors:
    def test_unsupported_format_returns_error(
        self, specialist: DataSpecialist, sample_md: Path, tmp_path: Path
    ):
        out = tmp_path / "out.docx"
        result = specialist.convert(sample_md, out, "docx")

        assert result.success is False
        assert result.output_path == out
        assert len(result.errors) == 1
        err = result.errors[0]
        assert err.code == "UNSUPPORTED_FORMAT"
        assert "docx" in err.message

    def test_importerror_wrapped_as_missing_dependency(
        self, specialist: DataSpecialist, sample_md: Path, tmp_path: Path
    ):
        out = tmp_path / "out.xlsx"
        with patch("orf.agents.specialists.data_specialist.MD2XLSXConverter") as MockConv:
            # Constructor raises ImportError (simulating missing openpyxl)
            MockConv.side_effect = ImportError("No module named openpyxl")

            result = specialist.convert(sample_md, out, "xlsx")

        assert result.success is False
        assert result.output_path == out
        assert len(result.errors) == 1
        err = result.errors[0]
        assert err.code == "MISSING_DEPENDENCY"
        assert "openpyxl" in err.message

    def test_importerror_csv(self, specialist: DataSpecialist, sample_md: Path, tmp_path: Path):
        out = tmp_path / "out.csv"
        with patch("orf.agents.specialists.data_specialist.MD2CSVConverter") as MockConv:
            MockConv.side_effect = ImportError("csv lib missing")

            result = specialist.convert(sample_md, out, "csv")

        assert result.success is False
        assert result.errors[0].code == "MISSING_DEPENDENCY"

    def test_importerror_json(self, specialist: DataSpecialist, sample_md: Path, tmp_path: Path):
        out = tmp_path / "out.json"
        with patch("orf.agents.specialists.data_specialist.MD2JSONConverter") as MockConv:
            MockConv.side_effect = ImportError("json lib missing")

            result = specialist.convert(sample_md, out, "json")

        assert result.success is False
        assert result.errors[0].code == "MISSING_DEPENDENCY"

    def test_generic_exception_wrapped_as_conversion_error(
        self, specialist: DataSpecialist, sample_md: Path, tmp_path: Path
    ):
        out = tmp_path / "out.xlsx"
        with patch("orf.agents.specialists.data_specialist.MD2XLSXConverter") as MockConv:
            MockConv.side_effect = RuntimeError("unexpected boom")

            result = specialist.convert(sample_md, out, "xlsx")

        assert result.success is False
        assert result.output_path == out
        err = result.errors[0]
        assert err.code == "CONVERSION_ERROR"
        assert "unexpected boom" in err.message


# =============================================================================
# convert — output_path defaulting
# =============================================================================


class TestDataSpecialistOutputPathDefault:
    def test_output_path_none_defaults_to_input_suffix(
        self, specialist: DataSpecialist, sample_md: Path
    ):
        with patch("orf.agents.specialists.data_specialist.MD2CSVConverter") as MockConv:
            instance = MagicMock()
            captured = {}

            def fake_convert(inp, out, opts=None, **kw):
                captured["inp"] = inp
                captured["out"] = out
                return _ok(out)

            instance.convert.side_effect = fake_convert
            MockConv.return_value = instance

            result = specialist.convert(sample_md, None, "csv")

        assert captured["out"] == sample_md.with_suffix(".csv")
        assert result.output_path == sample_md.with_suffix(".csv")
        assert result.success is True
