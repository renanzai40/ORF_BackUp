"""Tests for the FormatSpecialist agent.

Covers:
- supported_formats
- happy paths for docx / odt / epub
- UNSUPPORTED_FORMAT for pptx and unknown formats
- Generic Exception → CONVERSION_ERROR wrapping
- output_path defaulting behavior
- BaseSpecialist hooks (can_handle, category, get_capabilities)

All MD2*Converter instances are mocked at the
``orf.agents.specialists.format_specialist`` boundary so no real pandoc / library
calls happen.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orf.agents.specialists.format_specialist import FormatSpecialist
from orf.converters.base import ConversionResult, ErrorDetail


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    md = tmp_path / "in.md"
    md.write_text("# Title\n\nHello world.\n", encoding="utf-8")
    return md


@pytest.fixture
def specialist() -> FormatSpecialist:
    return FormatSpecialist()


def _ok(output: Path) -> ConversionResult:
    return ConversionResult(output_path=output, success=True)


# =============================================================================
# supported_formats / can_handle / category / get_capabilities
# =============================================================================


class TestFormatSpecialistInterface:
    EXPECTED_FORMATS = [
        "docx", "odt", "epub", "pptx", "rtf", "pdf", "icml", "srt",
        "csv", "xlsx", "json", "ipynb", "eml", "msg", "html", "xml",
    ]

    def test_supported_formats(self, specialist: FormatSpecialist):
        assert specialist.supported_formats == self.EXPECTED_FORMATS

    @pytest.mark.parametrize("fmt", EXPECTED_FORMATS)
    def test_can_handle_supported(self, specialist: FormatSpecialist, fmt: str):
        assert specialist.can_handle(fmt) is True

    def test_can_handle_unsupported(self, specialist: FormatSpecialist):
        assert specialist.can_handle("xyz") is False

    def test_category(self, specialist: FormatSpecialist):
        assert specialist.category == "format"

    def test_get_capabilities(self, specialist: FormatSpecialist):
        caps = specialist.get_capabilities()
        assert caps["category"] == "format"
        assert caps["formats"] == self.EXPECTED_FORMATS
        assert caps["supports_batch"] is True


# =============================================================================
# convert — happy paths
# =============================================================================


class TestFormatSpecialistConvertHappy:
    def test_convert_docx(self, specialist: FormatSpecialist, sample_md: Path, tmp_path: Path):
        out = tmp_path / "out.docx"
        with patch(
            "orf.agents.specialists.format_specialist.MD2DOCXConverter"
        ) as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            result = specialist.convert(sample_md, out, "docx")

        assert result.success is True
        assert result.output_path == out
        instance.convert.assert_called_once()
        # First positional arg of call should be the input path
        call_args = instance.convert.call_args[0]
        assert call_args[0] == sample_md
        assert call_args[1] == out

    def test_convert_odt(self, specialist: FormatSpecialist, sample_md: Path, tmp_path: Path):
        out = tmp_path / "out.odt"
        with patch("orf.agents.specialists.format_specialist.MD2ODTConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            result = specialist.convert(sample_md, out, "odt")

        assert result.success is True
        assert result.output_path == out

    def test_convert_epub(self, specialist: FormatSpecialist, sample_md: Path, tmp_path: Path):
        out = tmp_path / "out.epub"
        with patch("orf.agents.specialists.format_specialist.MD2EPUBConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            result = specialist.convert(sample_md, out, "epub")

        assert result.success is True
        assert result.output_path == out


# =============================================================================
# convert — error paths
# =============================================================================


class TestFormatSpecialistConvertErrors:
    def test_pptx_returns_unsupported_format(
        self, specialist: FormatSpecialist, sample_md: Path, tmp_path: Path
    ):
        out = tmp_path / "out.pptx"
        result = specialist.convert(sample_md, out, "pptx")

        assert result.success is False
        assert result.output_path == out
        assert len(result.errors) == 1
        err = result.errors[0]
        assert err.code == "UNSUPPORTED_FORMAT"
        assert "pptx" in err.message

    def test_unknown_format_returns_unsupported(
        self, specialist: FormatSpecialist, sample_md: Path, tmp_path: Path
    ):
        out = tmp_path / "out.xyz"
        result = specialist.convert(sample_md, out, "xyz")

        assert result.success is False
        assert result.errors[0].code == "UNSUPPORTED_FORMAT"

    def test_generic_exception_wrapped_as_conversion_error(
        self, specialist: FormatSpecialist, sample_md: Path, tmp_path: Path
    ):
        out = tmp_path / "out.docx"
        with patch(
            "orf.agents.specialists.format_specialist.MD2DOCXConverter"
        ) as MockConv:
            MockConv.side_effect = RuntimeError("boom")

            result = specialist.convert(sample_md, out, "docx")

        assert result.success is False
        assert result.output_path == out
        assert len(result.errors) == 1
        err = result.errors[0]
        assert err.code == "CONVERSION_ERROR"
        assert "boom" in err.message


# =============================================================================
# convert — output_path defaulting
# =============================================================================


class TestFormatSpecialistOutputPathDefault:
    def test_output_path_none_defaults_to_input_suffix(
        self, specialist: FormatSpecialist, sample_md: Path
    ):
        with patch(
            "orf.agents.specialists.format_specialist.MD2DOCXConverter"
        ) as MockConv:
            instance = MagicMock()

            # capture the output path actually passed to the underlying converter
            captured = {}

            def fake_convert(inp, out, opts=None, **kw):
                captured["inp"] = inp
                captured["out"] = out
                return _ok(out)

            instance.convert.side_effect = fake_convert
            MockConv.return_value = instance

            result = specialist.convert(sample_md, None, "docx")

        # Specialist should have constructed default output_path = sample_md.with_suffix('.docx')
        assert captured["out"] == sample_md.with_suffix(".docx")
        # And the wrapper returns that path on the result
        assert result.output_path == sample_md.with_suffix(".docx")
        assert result.success is True
