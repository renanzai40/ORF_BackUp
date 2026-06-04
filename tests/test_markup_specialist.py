"""Tests for the MarkupSpecialist agent.

Covers:
- supported_formats
- happy paths for html / xml
- UNSUPPORTED_FORMAT for unknown formats
- Generic Exception → CONVERSION_ERROR
- output_path defaulting behavior
- BaseSpecialist hooks (can_handle, category, get_capabilities)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orf.agents.specialists.markup_specialist import MarkupSpecialist
from orf.converters.base import ConversionResult


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    md = tmp_path / "in.md"
    md.write_text("# Title\n\nHello *world*.\n", encoding="utf-8")
    return md


@pytest.fixture
def specialist() -> MarkupSpecialist:
    return MarkupSpecialist()


def _ok(output: Path) -> ConversionResult:
    return ConversionResult(output_path=output, success=True)


# =============================================================================
# Interface
# =============================================================================


class TestMarkupSpecialistInterface:
    def test_supported_formats(self, specialist: MarkupSpecialist):
        assert specialist.supported_formats == ["xml", "html"]

    @pytest.mark.parametrize("fmt", ["xml", "html"])
    def test_can_handle_supported(self, specialist: MarkupSpecialist, fmt: str):
        assert specialist.can_handle(fmt) is True

    def test_can_handle_unsupported(self, specialist: MarkupSpecialist):
        assert specialist.can_handle("docx") is False
        assert specialist.can_handle("json") is False

    def test_category(self, specialist: MarkupSpecialist):
        assert specialist.category == "markup"

    def test_get_capabilities(self, specialist: MarkupSpecialist):
        caps = specialist.get_capabilities()
        assert caps["category"] == "markup"
        assert caps["formats"] == ["xml", "html"]
        assert caps["supports_batch"] is True


# =============================================================================
# convert — happy paths
# =============================================================================


class TestMarkupSpecialistConvertHappy:
    def test_convert_html(self, specialist: MarkupSpecialist, sample_md: Path, tmp_path: Path):
        out = tmp_path / "out.html"
        with patch("orf.agents.specialists.markup_specialist.MD2HTMLConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            result = specialist.convert(sample_md, out, "html")

        assert result.success is True
        assert result.output_path == out
        instance.convert.assert_called_once()

    def test_convert_xml(self, specialist: MarkupSpecialist, sample_md: Path, tmp_path: Path):
        out = tmp_path / "out.xml"
        with patch("orf.agents.specialists.markup_specialist.MD2XMLConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            result = specialist.convert(sample_md, out, "xml")

        assert result.success is True
        assert result.output_path == out


# =============================================================================
# convert — error paths
# =============================================================================


class TestMarkupSpecialistConvertErrors:
    def test_unsupported_format_returns_error(
        self, specialist: MarkupSpecialist, sample_md: Path, tmp_path: Path
    ):
        out = tmp_path / "out.docx"
        result = specialist.convert(sample_md, out, "docx")

        assert result.success is False
        assert result.output_path == out
        assert len(result.errors) == 1
        err = result.errors[0]
        assert err.code == "UNSUPPORTED_FORMAT"
        assert "docx" in err.message

    def test_unsupported_format_json(
        self, specialist: MarkupSpecialist, sample_md: Path, tmp_path: Path
    ):
        out = tmp_path / "out.json"
        result = specialist.convert(sample_md, out, "json")

        assert result.success is False
        assert result.errors[0].code == "UNSUPPORTED_FORMAT"

    def test_generic_exception_wrapped_as_conversion_error(
        self, specialist: MarkupSpecialist, sample_md: Path, tmp_path: Path
    ):
        out = tmp_path / "out.html"
        with patch("orf.agents.specialists.markup_specialist.MD2HTMLConverter") as MockConv:
            MockConv.side_effect = RuntimeError("pandoc died")

            result = specialist.convert(sample_md, out, "html")

        assert result.success is False
        assert result.output_path == out
        err = result.errors[0]
        assert err.code == "CONVERSION_ERROR"
        assert "pandoc died" in err.message


# =============================================================================
# convert — output_path defaulting
# =============================================================================


class TestMarkupSpecialistOutputPathDefault:
    def test_output_path_none_defaults_to_input_suffix(
        self, specialist: MarkupSpecialist, sample_md: Path
    ):
        with patch("orf.agents.specialists.markup_specialist.MD2XMLConverter") as MockConv:
            instance = MagicMock()
            captured = {}

            def fake_convert(inp, out, **opts):
                captured["inp"] = inp
                captured["out"] = out
                return _ok(out)

            instance.convert.side_effect = fake_convert
            MockConv.return_value = instance

            result = specialist.convert(sample_md, None, "xml")

        assert captured["out"] == sample_md.with_suffix(".xml")
        assert result.output_path == sample_md.with_suffix(".xml")
        assert result.success is True
