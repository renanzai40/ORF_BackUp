"""Integration tests: ForemanAgent → Specialist → mocked channel converter.

Covers:
- Foreman routes a docx job → FormatSpecialist → returns expected output
- Foreman routes an xlsx job → DataSpecialist
- Foreman routes an xml job → MarkupSpecialist
- Foreman routes an eml job → EmailSpecialist
- Foreman with an unknown format → falls back to "format" specialist
- Foreman aggregates errors from a failing specialist into JobResult.errors
- Foreman aggregates warnings
- Foreman's process_job success flag is False when errors present
- Complexity is propagated into JobResult.complexity

All channel converters (MD2*Converter) are mocked at their respective specialist
module boundary so no real conversion / network / pandoc call happens.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orf.agents.foreman import ForemanAgent, JobComplexity, JobRequest, JobResult
from orf.converters.base import ConversionResult, ErrorDetail, WarningDetail


# =============================================================================
# Helpers
# =============================================================================


def _ok(output: Path) -> ConversionResult:
    return ConversionResult(output_path=output, success=True)


def _fail(output: Path, code: str = "CONVERSION_ERROR", msg: str = "fail") -> ConversionResult:
    return ConversionResult(
        output_path=output,
        success=False,
        errors=[ErrorDetail(code=code, message=msg)],
    )


def _ok_with_warning(output: Path, code: str = "W", msg: str = "be careful") -> ConversionResult:
    return ConversionResult(
        output_path=output,
        success=True,
        warnings=[WarningDetail(code=code, message=msg)],
    )


# =============================================================================
# Routing: every format → correct specialist
# =============================================================================


class TestForemanRouting:
    """End-to-end: process_job → routed specialist → mocked channel converter."""

    def setup_method(self):
        self.foreman = ForemanAgent()

    def test_docx_routes_to_format_specialist(self, tmp_path: Path):
        out = tmp_path / "out.docx"
        with patch("orf.agents.specialists.format_specialist.MD2DOCXConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="docx",
                output_path=str(out),
            )
            result = self.foreman.process_job(job)

        assert result.success is True
        assert str(out) in result.output_paths
        instance.convert.assert_called_once()

    def test_xlsx_routes_to_data_specialist(self, tmp_path: Path):
        out = tmp_path / "out.xlsx"
        with patch("orf.agents.specialists.data_specialist.MD2XLSXConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="xlsx",
                output_path=str(out),
            )
            result = self.foreman.process_job(job)

        assert result.success is True
        assert str(out) in result.output_paths
        instance.convert.assert_called_once()

    def test_xml_routes_to_markup_specialist(self, tmp_path: Path):
        out = tmp_path / "out.xml"
        with patch("orf.agents.specialists.markup_specialist.MD2XMLConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="xml",
                output_path=str(out),
            )
            result = self.foreman.process_job(job)

        assert result.success is True
        assert str(out) in result.output_paths
        instance.convert.assert_called_once()

    def test_eml_routes_to_email_specialist(self, tmp_path: Path):
        out = tmp_path / "out.eml"
        with patch("orf.agents.specialists.email_specialist.MD2EMLConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="eml",
                output_path=str(out),
            )
            result = self.foreman.process_job(job)

        assert result.success is True
        assert str(out) in result.output_paths
        instance.convert.assert_called_once()

    def test_unknown_format_falls_back_to_format_specialist(self, tmp_path: Path):
        out = tmp_path / "out.docx"  # formatter will re-suffix to "out.xyz"
        with patch("orf.agents.specialists.format_specialist.MD2DOCXConverter") as MockConv:
            instance = MagicMock()
            # The "format" specialist receives "xyz" which it doesn't know —
            # it returns UNSUPPORTED_FORMAT, which the foreman aggregates.
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="xyz",
                output_path=str(out),
            )
            result = self.foreman.process_job(job)

        # Format specialist returns UNSUPPORTED_FORMAT → job fails
        assert result.success is False
        assert any(
            e.code == "UNSUPPORTED_FORMAT" for e in result.errors
        )

    def test_html_routes_to_markup_specialist(self, tmp_path: Path):
        out = tmp_path / "out.html"
        with patch("orf.agents.specialists.markup_specialist.MD2HTMLConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="html",
                output_path=str(out),
            )
            result = self.foreman.process_job(job)

        assert result.success is True
        assert str(out) in result.output_paths

    def test_csv_routes_to_data_specialist(self, tmp_path: Path):
        out = tmp_path / "out.csv"
        with patch("orf.agents.specialists.data_specialist.MD2CSVConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="csv",
                output_path=str(out),
            )
            result = self.foreman.process_job(job)

        assert result.success is True
        assert str(out) in result.output_paths


# =============================================================================
# Aggregation behavior
# =============================================================================


class TestForemanAggregation:
    def setup_method(self):
        self.foreman = ForemanAgent()

    def test_aggregates_errors_from_failing_specialist(self, tmp_path: Path):
        out = tmp_path / "out.docx"
        with patch("orf.agents.specialists.format_specialist.MD2DOCXConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _fail(
                out, code="CONVERSION_ERROR", msg="bad input"
            )
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="docx",
                output_path=str(out),
            )
            result = self.foreman.process_job(job)

        assert result.success is False
        assert len(result.errors) == 1
        assert result.errors[0].code == "CONVERSION_ERROR"
        assert result.errors[0].message == "bad input"
        # No outputs on failure
        assert result.output_paths == []

    def test_aggregates_warnings_from_successful_specialist(self, tmp_path: Path):
        out = tmp_path / "out.docx"
        with patch("orf.agents.specialists.format_specialist.MD2DOCXConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok_with_warning(
                out, code="LAYOUT_WARNING", msg="layout overflowed"
            )
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="docx",
                output_path=str(out),
            )
            result = self.foreman.process_job(job)

        assert result.success is True
        assert len(result.warnings) == 1
        assert result.warnings[0].code == "LAYOUT_WARNING"
        assert result.warnings[0].message == "layout overflowed"
        # Outputs still present on success-with-warnings
        assert str(out) in result.output_paths

    def test_success_flag_false_when_errors_present(self, tmp_path: Path):
        out = tmp_path / "out.xlsx"
        with patch("orf.agents.specialists.data_specialist.MD2XLSXConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _fail(out, code="MISSING_DEPENDENCY", msg="openpyxl?")
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="xlsx",
                output_path=str(out),
            )
            result = self.foreman.process_job(job)

        assert result.success is False
        assert any(e.code == "MISSING_DEPENDENCY" for e in result.errors)

    def test_success_flag_true_when_no_errors(self, tmp_path: Path):
        out = tmp_path / "out.xml"
        with patch("orf.agents.specialists.markup_specialist.MD2XMLConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="xml",
                output_path=str(out),
            )
            result = self.foreman.process_job(job)

        assert result.success is True
        assert result.errors == []
        assert result.output_paths == [str(out)]

    def test_complexity_propagated_to_result_simple(self, tmp_path: Path):
        out = tmp_path / "out.eml"
        with patch("orf.agents.specialists.email_specialist.MD2EMLConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="eml",
                output_path=str(out),
                # SIMPLE: single file, small
                is_batch=False, file_count=1, estimated_size_mb=10.0,
            )
            result = self.foreman.process_job(job)

        assert result.complexity == JobComplexity.SIMPLE
        assert result.success is True

    def test_complexity_propagated_to_result_complex(self, tmp_path: Path):
        out = tmp_path / "out.docx"
        with patch("orf.agents.specialists.format_specialist.MD2DOCXConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="docx",
                output_path=str(out),
                # COMPLEX: large file, single, not batch
                is_batch=False, file_count=1, estimated_size_mb=120.0,
            )
            result = self.foreman.process_job(job)

        assert result.complexity == JobComplexity.COMPLEX
        assert result.success is True
        assert str(out) in result.output_paths

    def test_complexity_propagated_to_result_moderate(self, tmp_path: Path):
        out = tmp_path / "out.csv"
        with patch("orf.agents.specialists.data_specialist.MD2CSVConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok(out)
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="csv",
                output_path=str(out),
                is_batch=True,  # → MODERATE
                file_count=1, estimated_size_mb=10.0,
            )
            result = self.foreman.process_job(job)

        assert result.complexity == JobComplexity.MODERATE
        assert result.success is True

    def test_full_jobresult_shape_on_success(self, tmp_path: Path):
        out = tmp_path / "out.html"
        with patch("orf.agents.specialists.markup_specialist.MD2HTMLConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _ok_with_warning(out)
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="html",
                output_path=str(out),
            )
            result: JobResult = self.foreman.process_job(job)

        # All fields are populated
        assert isinstance(result, JobResult)
        assert result.success is True
        assert result.output_paths == [str(out)]
        assert len(result.warnings) == 1
        assert result.errors == []
        assert result.complexity == JobComplexity.SIMPLE
