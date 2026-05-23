"""Conversion error classes and recovery strategies for ORF Phase 1."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ConversionError(Exception):
    """Base exception for all conversion errors in ORF pipeline."""

    def __init__(self, message: str, context: Optional["ErrorContext"] = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r}, context={self.context})"


class SkeletonNotFoundError(ConversionError):
    """Raised when a skeleton file cannot be located during conversion."""

    def __init__(
        self, skeleton_path: str, search_locations: Optional[list[str]] = None
    ) -> None:
        self.skeleton_path = skeleton_path
        self.search_locations = search_locations or []
        message = f"Skeleton not found: {skeleton_path}"
        super().__init__(message)


class TranslationUnitNotFoundError(ConversionError):
    """Raised when a translation unit (segment) is missing from source."""

    def __init__(
        self, unit_id: str, source_document: Optional[str] = None
    ) -> None:
        self.unit_id = unit_id
        self.source_document = source_document
        message = f"Translation unit not found: {unit_id}"
        super().__init__(message)


class ManifestParseError(ConversionError):
    """Raised when manifest.yaml or orf.yaml cannot be parsed."""

    def __init__(
        self, manifest_path: str, reason: str, line_number: Optional[int] = None
    ) -> None:
        self.manifest_path = manifest_path
        self.reason = reason
        self.line_number = line_number
        location = f" line {line_number}" if line_number else ""
        message = f"Manifest parse error in {manifest_path}{location}: {reason}"
        super().__init__(message)


class XLIFFParseError(ConversionError):
    """Raised when an XLIFF file cannot be parsed or is malformed."""

    def __init__(
        self, xliff_path: str, reason: str, line_number: Optional[int] = None
    ) -> None:
        self.xliff_path = xliff_path
        self.reason = reason
        self.line_number = line_number
        location = f" line {line_number}" if line_number else ""
        message = f"XLIFF parse error in {xliff_path}{location}: {reason}"
        super().__init__(message)


class InlineFormattingError(ConversionError):
    """Raised when inline formatting tags cannot be properly handled."""

    def __init__(
        self, tag: str, context: str, original_segment: Optional[str] = None
    ) -> None:
        self.tag = tag
        self.context = context
        self.original_segment = original_segment
        message = f"Inline formatting error with tag '{tag}' in context: {context}"
        super().__init__(message)


class FormatDetectionError(ConversionError):
    """Raised when format cannot be automatically detected."""

    def __init__(self, file_path: str, reason: str) -> None:
        self.file_path = file_path
        self.reason = reason
        message = f"Cannot detect format for '{file_path}': {reason}"
        super().__init__(message)


class ResourceManagementError(ConversionError):
    """Raised for image/resource management failures."""

    def __init__(self, resource_path: str, operation: str, reason: str) -> None:
        self.resource_path = resource_path
        self.operation = operation
        self.reason = reason
        message = f"Resource management error during '{operation}' on '{resource_path}': {reason}"
        super().__init__(message)


class RecoveryStrategy(Enum):
    """Strategies for recovering from conversion errors."""

    RETRY = "retry"
    """Retry the failed operation with same parameters."""

    SKIP = "skip"
    """Skip the failed item and continue processing."""

    FALLBACK = "fallback"
    """Use a fallback mechanism or default value."""

    ABORT = "abort"
    """Abort the entire conversion process."""

    PARTIAL = "partial"
    """Produce partial output and continue."""

    MANUAL_INTERVENTION = "manual_intervention"
    """Require manual intervention to resolve."""


@dataclass
class ErrorContext:
    """Context information for conversion errors."""

    file_path: Optional[str] = None
    """Path to the file being processed when error occurred."""

    line_number: Optional[int] = None
    """Line number in source file where error occurred."""

    segment_id: Optional[str] = None
    """Segment or unit identifier being processed."""

    operation: Optional[str] = None
    """The operation being performed when error occurred."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional contextual metadata."""

    def with_metadata(self, **kwargs: Any) -> "ErrorContext":
        """Add or update metadata and return a new ErrorContext."""
        new_metadata = {**self.metadata, **kwargs}
        return ErrorContext(
            file_path=self.file_path,
            line_number=self.line_number,
            segment_id=self.segment_id,
            operation=self.operation,
            metadata=new_metadata,
        )