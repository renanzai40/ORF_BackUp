"""Format Specialist - handles DOCX, PPTX, ODT, EPUB conversions."""

from pathlib import Path
from typing import Optional

from orf.agents.specialists.base import BaseSpecialist
from orf.converters.base import ConversionResult, ErrorDetail
from orf.channels.md2docx import MD2DOCXConverter
from orf.channels.md2odt import MD2ODTConverter
from orf.channels.md2epub import MD2EPUBConverter


class FormatSpecialist(BaseSpecialist):
    """Handles office format conversions with skeleton backfill.

    Formats: docx, pptx, odt, epub
    """

    @property
    def supported_formats(self) -> list[str]:
        return ["docx", "odt", "epub", "pptx"]

    def convert(
        self,
        input_path: Path,
        output_path: Optional[Path],
        target_format: str,
        **options
    ) -> ConversionResult:
        """Convert MD to office format using appropriate converter."""
        if output_path is None:
            output_path = input_path.with_suffix(f".{target_format}")

        try:
            if target_format == "docx":
                converter = MD2DOCXConverter()
            elif target_format == "odt":
                converter = MD2ODTConverter()
            elif target_format == "epub":
                converter = MD2EPUBConverter()
            else:
                return ConversionResult(
                    output_path=output_path,
                    success=False,
                    errors=[ErrorDetail(
                        code="UNSUPPORTED_FORMAT",
                        message=f"Format {target_format} not supported by FormatSpecialist"
                    )]
                )

            return converter.convert(input_path, output_path, **options)

        except Exception as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[ErrorDetail(
                    code="CONVERSION_ERROR",
                    message=str(e)
                )]
            )