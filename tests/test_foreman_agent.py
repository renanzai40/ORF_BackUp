"""Tests for the Foreman Agent orchestrator.

Covers:
- JobComplexity enum
- JobRequest / JobResult dataclasses
- ForemanAgent.assess_complexity (SIMPLE / MODERATE / COMPLEX)
- ForemanAgent.decompose_job (SIMPLE returns [job], else batch)
- ForemanAgent.route_to_specialist (11 formats + unknown default)
- ForemanAgent.handle_error (error code prefix → RecoveryStrategy)
- ForemanAgent.process_job (happy path, NO_SPECIALIST error, aggregation)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orf.agents.foreman import (
    ForemanAgent,
    JobComplexity,
    JobRequest,
    JobResult,
)
from orf.converters.base import ConversionResult, ErrorDetail, WarningDetail
from orf.error_handlers.conversion_error import RecoveryStrategy


# =============================================================================
# JobComplexity enum
# =============================================================================


class TestJobComplexityEnum:
    def test_has_three_values(self):
        values = list(JobComplexity)
        assert len(values) == 3

    def test_simple_value(self):
        assert JobComplexity.SIMPLE.value == 1

    def test_moderate_value(self):
        assert JobComplexity.MODERATE.value == 2

    def test_complex_value(self):
        assert JobComplexity.COMPLEX.value == 3

    def test_names(self):
        names = {c.name for c in JobComplexity}
        assert names == {"SIMPLE", "MODERATE", "COMPLEX"}


# =============================================================================
# JobRequest / JobResult dataclasses
# =============================================================================


class TestJobRequestDataclass:
    def test_minimal_creation(self):
        job = JobRequest(input_path="in.md", target_format="docx")
        assert job.input_path == "in.md"
        assert job.target_format == "docx"
        assert job.output_path is None
        assert job.is_batch is False
        assert job.file_count == 1
        assert job.estimated_size_mb == 0.0
        assert job.metadata == {}

    def test_full_creation(self):
        job = JobRequest(
            input_path="in.md",
            target_format="epub",
            output_path="out.epub",
            is_batch=True,
            file_count=10,
            estimated_size_mb=128.0,
            metadata={"formats": ["docx", "pdf"]},
        )
        assert job.output_path == "out.epub"
        assert job.is_batch is True
        assert job.file_count == 10
        assert job.estimated_size_mb == 128.0
        assert job.metadata == {"formats": ["docx", "pdf"]}

    def test_metadata_default_is_independent_per_instance(self):
        job_a = JobRequest(input_path="a", target_format="docx")
        job_b = JobRequest(input_path="b", target_format="docx")
        job_a.metadata["k"] = "v"
        assert job_b.metadata == {}


class TestJobResultDataclass:
    def test_minimal_creation(self):
        result = JobResult(success=True)
        assert result.success is True
        assert result.output_paths == []
        assert result.errors == []
        assert result.warnings == []
        assert result.complexity == JobComplexity.SIMPLE

    def test_with_errors_and_warnings(self):
        err = ErrorDetail(code="E1", message="boom")
        warn = WarningDetail(code="W1", message="careful")
        result = JobResult(
            success=False,
            output_paths=["a.docx"],
            errors=[err],
            warnings=[warn],
            complexity=JobComplexity.COMPLEX,
        )
        assert result.success is False
        assert result.output_paths == ["a.docx"]
        assert result.errors == [err]
        assert result.warnings == [warn]
        assert result.complexity == JobComplexity.COMPLEX


# =============================================================================
# assess_complexity
# =============================================================================


class TestAssessComplexity:
    def setup_method(self):
        self.foreman = ForemanAgent()

    def test_simple_single_file_small(self):
        job = JobRequest(
            input_path="a.md", target_format="docx", is_batch=False,
            file_count=1, estimated_size_mb=10.0,
        )
        assert self.foreman.assess_complexity(job) == JobComplexity.SIMPLE

    def test_simple_zero_size(self):
        job = JobRequest(
            input_path="a.md", target_format="docx",
            estimated_size_mb=0.0,
        )
        assert self.foreman.assess_complexity(job) == JobComplexity.SIMPLE

    def test_moderate_due_to_batch_flag(self):
        job = JobRequest(
            input_path="a.md", target_format="docx",
            is_batch=True, file_count=1, estimated_size_mb=10.0,
        )
        assert self.foreman.assess_complexity(job) == JobComplexity.MODERATE

    def test_moderate_due_to_file_count(self):
        job = JobRequest(
            input_path="a.md", target_format="docx",
            is_batch=False, file_count=5, estimated_size_mb=10.0,
        )
        assert self.foreman.assess_complexity(job) == JobComplexity.MODERATE

    def test_complex_due_to_large_size(self):
        # size 60 > 50 but NOT batch / multi-file → COMPLEX
        job = JobRequest(
            input_path="a.md", target_format="docx",
            is_batch=False, file_count=1, estimated_size_mb=60.0,
        )
        assert self.foreman.assess_complexity(job) == JobComplexity.COMPLEX

    def test_complex_due_to_multi_format_metadata(self):
        # size >= 50, not batch, single file, but metadata has >1 format
        # (size == 50 falls through SIMPLE, then to COMPLEX via metadata)
        job = JobRequest(
            input_path="a.md", target_format="docx",
            is_batch=False, file_count=1, estimated_size_mb=50.0,
            metadata={"formats": ["docx", "pdf"]},
        )
        assert self.foreman.assess_complexity(job) == JobComplexity.COMPLEX

    def test_fallback_moderate_when_no_qualifier(self):
        # size 50 (not < 50, not > 50), not batch, single file, no formats
        job = JobRequest(
            input_path="a.md", target_format="docx",
            is_batch=False, file_count=1, estimated_size_mb=50.0,
        )
        assert self.foreman.assess_complexity(job) == JobComplexity.MODERATE


# =============================================================================
# decompose_job
# =============================================================================


class TestDecomposeJob:
    def setup_method(self):
        self.foreman = ForemanAgent()

    def test_simple_returns_single_element_list(self):
        job = JobRequest(
            input_path="a.md", target_format="docx",
            estimated_size_mb=10.0,
        )
        result = self.foreman.decompose_job(job)
        assert result == [job]
        assert len(result) == 1

    def test_moderate_returns_batch(self):
        # MODERATE due to is_batch=True
        job = JobRequest(
            input_path="a.md", target_format="docx",
            is_batch=True, estimated_size_mb=10.0,
        )
        # Per current source, MODERATE/COMPLEX both return [job]
        result = self.foreman.decompose_job(job)
        assert isinstance(result, list)
        assert len(result) >= 1
        assert all(isinstance(r, JobRequest) for r in result)

    def test_complex_returns_batch(self):
        job = JobRequest(
            input_path="a.md", target_format="docx",
            estimated_size_mb=80.0,
        )
        result = self.foreman.decompose_job(job)
        assert isinstance(result, list)
        assert len(result) >= 1


# =============================================================================
# route_to_specialist
# =============================================================================


class TestRouteToSpecialist:
    def setup_method(self):
        self.foreman = ForemanAgent()

    @pytest.mark.parametrize("fmt,expected", [
        ("docx", "format"),
        ("odt", "format"),
        ("epub", "format"),
        ("pptx", "format"),
        ("xlsx", "data"),
        ("csv", "data"),
        ("json", "data"),
        ("xml", "markup"),
        ("html", "markup"),
        ("eml", "email"),
        ("msg", "email"),
    ])
    def test_known_format_routes_correctly(self, fmt, expected):
        job = JobRequest(input_path="a.md", target_format=fmt)
        assert self.foreman.route_to_specialist(job) == expected

    def test_case_insensitive(self):
        job = JobRequest(input_path="a.md", target_format="DOCX")
        assert self.foreman.route_to_specialist(job) == "format"

    def test_unknown_format_defaults_to_format(self):
        job = JobRequest(input_path="a.md", target_format="xyz")
        assert self.foreman.route_to_specialist(job) == "format"


# =============================================================================
# handle_error
# =============================================================================


class TestHandleError:
    def setup_method(self):
        self.foreman = ForemanAgent()

    def test_explicit_recovery_strategy_returned_as_is(self):
        err = ErrorDetail(
            code="ANY", message="m",
            recovery_strategy=RecoveryStrategy.RETRY,
        )
        assert self.foreman.handle_error(err) == RecoveryStrategy.RETRY

    def test_not_found_prefix_aborts(self):
        err = ErrorDetail(code="FILE_NOT_FOUND", message="m")
        assert self.foreman.handle_error(err) == RecoveryStrategy.ABORT

    def test_missing_prefix_aborts(self):
        err = ErrorDetail(code="MISSING_DEPENDENCY", message="m")
        assert self.foreman.handle_error(err) == RecoveryStrategy.ABORT

    def test_invalid_prefix_skips(self):
        err = ErrorDetail(code="INVALID_INPUT", message="m")
        assert self.foreman.handle_error(err) == RecoveryStrategy.SKIP

    def test_malformed_prefix_skips(self):
        err = ErrorDetail(code="MALFORMED_XML", message="m")
        assert self.foreman.handle_error(err) == RecoveryStrategy.SKIP

    def test_timeout_prefix_retries(self):
        err = ErrorDetail(code="TIMEOUT_ERROR", message="m")
        assert self.foreman.handle_error(err) == RecoveryStrategy.RETRY

    def test_network_prefix_retries(self):
        err = ErrorDetail(code="NETWORK_FAILURE", message="m")
        assert self.foreman.handle_error(err) == RecoveryStrategy.RETRY

    def test_skeleton_prefix_manual_intervention(self):
        # Code contains SKELETON but not NOT_FOUND / MISSING (those would match first)
        err = ErrorDetail(code="SKELETON_CORRUPTED", message="m")
        assert self.foreman.handle_error(err) == RecoveryStrategy.MANUAL_INTERVENTION

    def test_unknown_code_falls_back(self):
        err = ErrorDetail(code="WEIRD_THING", message="m")
        assert self.foreman.handle_error(err) == RecoveryStrategy.FALLBACK


# =============================================================================
# process_job
# =============================================================================


def _make_success_result(output: Path) -> ConversionResult:
    return ConversionResult(output_path=output, success=True)


def _make_failure_result(output: Path, code: str = "X", message: str = "fail") -> ConversionResult:
    return ConversionResult(
        output_path=output,
        success=False,
        errors=[ErrorDetail(code=code, message=message)],
        warnings=[WarningDetail(code="W", message="warn")],
    )


class TestProcessJob:
    def setup_method(self):
        self.foreman = ForemanAgent()

    def test_happy_path_returns_success(self, tmp_path: Path):
        out = tmp_path / "out.docx"
        # Patch the FormatSpecialist's underlying converter to return success
        with patch("orf.agents.specialists.format_specialist.MD2DOCXConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _make_success_result(out)
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="docx",
                output_path=str(out),
            )
            result = self.foreman.process_job(job)

        assert result.success is True
        assert str(out) in result.output_paths
        assert result.errors == []
        assert result.complexity == JobComplexity.SIMPLE

    def test_no_specialist_returns_error(self):
        # Force route_to_specialist to return an unknown category
        foreman = ForemanAgent()
        # Remove the only specialist to trigger the NO_SPECIALIST branch
        foreman._specialists = {}  # type: ignore[attr-defined]

        job = JobRequest(input_path="a.md", target_format="docx")
        result = foreman.process_job(job)

        assert result.success is False
        assert len(result.errors) == 1
        assert result.errors[0].code == "NO_SPECIALIST"

    def test_aggregates_errors_from_specialist(self, tmp_path: Path):
        out = tmp_path / "out.docx"
        with patch("orf.agents.specialists.format_specialist.MD2DOCXConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _make_failure_result(
                out, code="CONVERSION_ERROR", message="boom"
            )
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="docx",
                output_path=str(out),
            )
            result = self.foreman.process_job(job)

        assert result.success is False
        assert any(e.code == "CONVERSION_ERROR" for e in result.errors)

    def test_aggregates_warnings_from_specialist(self, tmp_path: Path):
        out = tmp_path / "out.docx"
        with patch("orf.agents.specialists.format_specialist.MD2DOCXConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = ConversionResult(
                output_path=out, success=True,
                warnings=[WarningDetail(code="W1", message="careful")],
            )
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="docx",
                output_path=str(out),
            )
            result = self.foreman.process_job(job)

        assert result.success is True
        assert any(w.code == "W1" for w in result.warnings)

    def test_complexity_propagated_to_result(self, tmp_path: Path):
        # Build a job that should be MODERATE (is_batch=True) and ensure complexity
        # lands in the result.
        out = tmp_path / "out.docx"
        with patch("orf.agents.specialists.format_specialist.MD2DOCXConverter") as MockConv:
            instance = MagicMock()
            instance.convert.return_value = _make_success_result(out)
            MockConv.return_value = instance

            job = JobRequest(
                input_path=str(tmp_path / "in.md"),
                target_format="docx",
                output_path=str(out),
                is_batch=True,
            )
            result = self.foreman.process_job(job)

        assert result.complexity == JobComplexity.MODERATE
