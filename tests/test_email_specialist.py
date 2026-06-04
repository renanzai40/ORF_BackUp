"""Tests for the EmailSpecialist agent.

Covers:
- supported_formats
- happy path for eml
- happy path for msg (guarded by pytest.importorskip("aspose.email"))
- ImportError → MISSING_DEPENDENCY (mocked via constructor raising)
- Generic Exception → CONVERSION_ERROR
- UNSUPPORTED_FORMAT for unknown formats
- output_path defaulting
- BaseSpecialist hooks
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orf.agents.specialists.email_specialist import EmailSpecialist
from orf.converters.base import ConversionResult


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    md = tmp_path / "in.md"
    md.write_text("# Subject\n\nBody line.\n", encoding="utf-8")
    return md


@pytest.fixture
def specialist() -> EmailSpecialist:
    return EmailSpecialist()


def _ok(output: Path) -> ConversionResult:
    return ConversionResult(output_path=output, success=True)


# =============================================================================
# Interface
# =============================================================================


class TestEmailSpecialistInterface:
    def test_supported_formats(self, specialist: EmailSpecialist):
        assert specialist.supported_formats == ["eml", "msg"]

    @pytest.mark.parametrize("fmt", ["eml", "msg"])
    def test_can_handle_supported(self, specialist: EmailSpecialist, fmt: str):
        assert specialist.can_handle(fmt) is True

    def test_can_handle_unsupported(self, specialist: EmailSpecialist):
        assert specialist.can_handle("docx") is False
        assert specialist.can_handle("html") is False

    def test_category(self, specialist: EmailSpecialist):
        assert specialist.category == "email"

    def test_get_capabilities(self, specialist: EmailSpecialist):
        caps = specialist.get_capabilities()
        assert caps["category"] == "email"
        assert caps["formats"] == ["eml", "msg"]
        assert caps["supports_batch"] is True


# =============================================================================
# convert — happy paths
# =============================================================================


class TestEmailSpecialistConvertHappy:
    def test_convert_eml(self, specialist: EmailSpecialist, sample_md: Path, tmp_path: Path):
        out = tmp_path / "out.eml"
        with patch("orf.agents.specialists.email_specialist.MD2EMLConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            result = specialist.convert(sample_md, out, "eml")

        assert result.success is True
        assert result.output_path == out
        instance.convert.assert_called_once()

    def test_convert_msg(self, specialist: EmailSpecialist, sample_md: Path, tmp_path: Path):
        # Source uses aspose.email; skip when absent.
        pytest.importorskip("aspose.email")
        out = tmp_path / "out.msg"
        with patch("orf.agents.specialists.email_specialist.MD2MSGConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            result = specialist.convert(sample_md, out, "msg")

        assert result.success is True
        assert result.output_path == out


# =============================================================================
# convert — error paths
# =============================================================================


class TestEmailSpecialistConvertErrors:
    def test_unsupported_format_returns_error(
        self, specialist: EmailSpecialist, sample_md: Path, tmp_path: Path
    ):
        out = tmp_path / "out.docx"
        result = specialist.convert(sample_md, out, "docx")

        assert result.success is False
        assert result.output_path == out
        assert len(result.errors) == 1
        err = result.errors[0]
        assert err.code == "UNSUPPORTED_FORMAT"
        assert "docx" in err.message

    def test_importerror_wrapped_as_missing_dependency_eml(
        self, specialist: EmailSpecialist, sample_md: Path, tmp_path: Path
    ):
        out = tmp_path / "out.eml"
        with patch("orf.agents.specialists.email_specialist.MD2EMLConverter") as MockConv:
            MockConv.side_effect = ImportError("aspose.email missing")

            result = specialist.convert(sample_md, out, "eml")

        assert result.success is False
        assert result.output_path == out
        err = result.errors[0]
        assert err.code == "MISSING_DEPENDENCY"
        assert "aspose.email" in err.message

    def test_importerror_wrapped_as_missing_dependency_msg(
        self, specialist: EmailSpecialist, sample_md: Path, tmp_path: Path
    ):
        # This test does NOT need aspose to be installed — we mock the constructor
        # so the real import never runs. It just simulates the aspose-missing scenario.
        out = tmp_path / "out.msg"
        with patch("orf.agents.specialists.email_specialist.MD2MSGConverter") as MockConv:
            MockConv.side_effect = ImportError("aspose.email not installed")

            result = specialist.convert(sample_md, out, "msg")

        assert result.success is False
        assert result.errors[0].code == "MISSING_DEPENDENCY"

    def test_generic_exception_wrapped_as_conversion_error(
        self, specialist: EmailSpecialist, sample_md: Path, tmp_path: Path
    ):
        out = tmp_path / "out.eml"
        with patch("orf.agents.specialists.email_specialist.MD2EMLConverter") as MockConv:
            MockConv.side_effect = RuntimeError("io failure")

            result = specialist.convert(sample_md, out, "eml")

        assert result.success is False
        assert result.output_path == out
        err = result.errors[0]
        assert err.code == "CONVERSION_ERROR"
        assert "io failure" in err.message

    def test_generic_exception_msg(
        self, specialist: EmailSpecialist, sample_md: Path, tmp_path: Path
    ):
        # Again, no real aspose needed — we mock the constructor.
        out = tmp_path / "out.msg"
        with patch("orf.agents.specialists.email_specialist.MD2MSGConverter") as MockConv:
            MockConv.side_effect = RuntimeError("msg failure")

            result = specialist.convert(sample_md, out, "msg")

        assert result.success is False
        assert result.errors[0].code == "CONVERSION_ERROR"


# =============================================================================
# convert — output_path defaulting
# =============================================================================


class TestEmailSpecialistOutputPathDefault:
    def test_output_path_none_defaults_to_input_suffix_eml(
        self, specialist: EmailSpecialist, sample_md: Path
    ):
        with patch("orf.agents.specialists.email_specialist.MD2EMLConverter") as MockConv:
            instance = MagicMock()
            captured = {}

            def fake_convert(inp, out, **opts):
                captured["inp"] = inp
                captured["out"] = out
                return _ok(out)

            instance.convert.side_effect = fake_convert
            MockConv.return_value = instance

            result = specialist.convert(sample_md, None, "eml")

        assert captured["out"] == sample_md.with_suffix(".eml")
        assert result.output_path == sample_md.with_suffix(".eml")
        assert result.success is True

    def test_output_path_none_defaults_to_input_suffix_msg(
        self, specialist: EmailSpecialist, sample_md: Path
    ):
        # No aspose needed: constructor is mocked.
        with patch("orf.agents.specialists.email_specialist.MD2MSGConverter") as MockConv:
            instance = MagicMock()
            captured = {}

            def fake_convert(inp, out, **opts):
                captured["inp"] = inp
                captured["out"] = out
                return _ok(out)

            instance.convert.side_effect = fake_convert
            MockConv.return_value = instance

            result = specialist.convert(sample_md, None, "msg")

        assert captured["out"] == sample_md.with_suffix(".msg")
        assert result.output_path == sample_md.with_suffix(".msg")
        assert result.success is True
