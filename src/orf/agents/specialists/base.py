"""Base specialist interface and shared utilities."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from orf.converters.base import ConversionResult


class BaseSpecialist(ABC):
    """Base class for all format specialists."""

    @property
    @abstractmethod
    def supported_formats(self) -> list[str]:
        """List of formats this specialist handles."""
        pass

    @property
    def category(self) -> str:
        """Category name for logging."""
        return self.__class__.__name__.replace("Specialist", "").lower()

    def can_handle(self, format: str) -> bool:
        """Check if this specialist handles the given format."""
        return format.lower() in self.supported_formats

    @abstractmethod
    def convert(
        self,
        input_path: Path,
        output_path: Optional[Path],
        target_format: str,
        **options
    ) -> ConversionResult:
        """Convert file to target format."""
        pass

    def get_capabilities(self) -> dict:
        """Return specialist capabilities."""
        return {
            "category": self.category,
            "formats": self.supported_formats,
            "supports_batch": True,
        }