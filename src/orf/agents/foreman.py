"""Foreman Agent - Job orchestration supervisor.

The Foreman analyzes incoming job requests, determines complexity,
decomposes into subtasks, and delegates to appropriate Specialists.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Any
from pathlib import Path

from orf.converters.base import ErrorDetail, WarningDetail
from orf.error_handlers.conversion_error import RecoveryStrategy


class JobComplexity(Enum):
    """Job complexity levels."""
    SIMPLE = 1      # Single file, known format
    MODERATE = 2    # Batch, or unknown format
    COMPLEX = 3     # Multi-format, large files


@dataclass
class JobRequest:
    """Incoming job request."""
    input_path: str
    target_format: str
    output_path: Optional[str] = None
    is_batch: bool = False
    file_count: int = 1
    estimated_size_mb: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobResult:
    """Result from job processing."""
    success: bool
    output_paths: list[str] = field(default_factory=list)
    errors: list[ErrorDetail] = field(default_factory=list)
    warnings: list[WarningDetail] = field(default_factory=list)
    complexity: JobComplexity = JobComplexity.SIMPLE


class ForemanAgent:
    """Orchestrates conversion jobs, delegates to Specialists.

    The Foreman is the central coordinator that:
    1. Receives job requests
    2. Assesses complexity (SIMPLE/MODERATE/COMPLEX)
    3. Decomposes into subtasks if needed
    4. Delegates to appropriate Specialists
    5. Aggregates results
    6. Handles errors via RecoveryStrategy
    """

    def __init__(self):
        self._specialists = self._init_specialists()

    def _init_specialists(self) -> dict:
        """Initialize specialist agents by category."""
        from orf.agents.specialists import (
            FormatSpecialist, DataSpecialist, MarkupSpecialist, EmailSpecialist
        )
        return {
            "format": FormatSpecialist(),
            "data": DataSpecialist(),
            "markup": MarkupSpecialist(),
            "email": EmailSpecialist(),
        }

    def assess_complexity(self, job: JobRequest) -> JobComplexity:
        """Assess job complexity based on job characteristics."""
        # SIMPLE: Single file, known format
        if not job.is_batch and job.file_count == 1 and job.estimated_size_mb < 50:
            return JobComplexity.SIMPLE

        # MODERATE: Batch or unknown format
        if job.is_batch or job.file_count > 1:
            return JobComplexity.MODERATE

        # COMPLEX: Large files or multi-format
        if job.estimated_size_mb > 50 or len(job.metadata.get("formats", [])) > 1:
            return JobComplexity.COMPLEX

        return JobComplexity.MODERATE

    def decompose_job(self, job: JobRequest) -> list[JobRequest]:
        """Decompose complex job into subtasks."""
        complexity = self.assess_complexity(job)

        if complexity == JobComplexity.SIMPLE:
            return [job]

        # For MODERATE/COMPLEX, could split by file or format
        # For now, return as-is (specialists handle their own batching)
        return [job]

    def route_to_specialist(self, job: JobRequest) -> str:
        """Route job to appropriate specialist based on target format."""
        format_to_category = {
            # Format specialists (office / document / publishing)
            "docx": "format", "odt": "format", "epub": "format", "pptx": "format",
            "rtf": "format", "pdf": "format", "icml": "format", "srt": "format",
            # Data specialists
            "xlsx": "data", "csv": "data", "json": "data", "ipynb": "data",
            # Markup specialists
            "xml": "markup", "html": "markup",
            # Email specialists
            "eml": "email", "msg": "email",
        }

        target = job.target_format.lower()
        return format_to_category.get(target, "format")

    def handle_error(self, error: ErrorDetail) -> RecoveryStrategy:
        """Determine recovery strategy for an error."""
        if error.recovery_strategy:
            return error.recovery_strategy

        # Default strategies by error code prefix
        error_code = error.code.upper()

        if "NOT_FOUND" in error_code or "MISSING" in error_code:
            return RecoveryStrategy.ABORT
        if "INVALID" in error_code or "MALFORMED" in error_code:
            return RecoveryStrategy.SKIP
        if "TIMEOUT" in error_code or "NETWORK" in error_code:
            return RecoveryStrategy.RETRY
        if "SKELETON" in error_code:
            return RecoveryStrategy.MANUAL_INTERVENTION

        return RecoveryStrategy.FALLBACK

    def process_job(self, job: JobRequest) -> JobResult:
        """Process a job request through the agent pipeline."""
        # Assess complexity
        complexity = self.assess_complexity(job)

        # Route to specialist
        specialist_name = self.route_to_specialist(job)
        specialist = self._specialists.get(specialist_name)

        if not specialist:
            return JobResult(
                success=False,
                errors=[ErrorDetail(
                    code="NO_SPECIALIST",
                    message=f"No specialist found for format: {job.target_format}"
                )]
            )

        # Decompose if needed
        subtasks = self.decompose_job(job)

        # Process each subtask
        all_errors = []
        all_warnings = []
        all_outputs = []

        for subtask in subtasks:
            result = specialist.convert(
                Path(subtask.input_path),
                Path(subtask.output_path) if subtask.output_path else None,
                subtask.target_format
            )

            if result.success:
                all_outputs.append(str(result.output_path))
            else:
                all_errors.extend(result.errors)

            all_warnings.extend(result.warnings)

        return JobResult(
            success=len(all_errors) == 0,
            output_paths=all_outputs,
            errors=all_errors,
            warnings=all_warnings,
            complexity=complexity
        )