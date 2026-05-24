"""Markup Specialist - handles XML, HTML conversions."""

from pathlib import Path
from typing import Optional

from orf.agents.specialists.base import BaseSpecialist
from orf.converters.base import ConversionResult, ErrorDetail
from orf.channels.md2html import MD2HTMLConverter
from orf.channels.md2xml import MD2XMLConverter


class MarkupSpecialist(BaseSpecialist):
    """Handles markup format conversions.

    Formats: xml, html
    """

    @property
    def supported_formats(self) -> list[str]:
        return ["xml", "html"]

    def convert(
        self,
        input_path: Path,
        output_path: Optional[Path],
        target_format: str,
        **options
    ) -> ConversionResult:
        """Convert MD to markup format."""
        if output_path is None:
            output_path = input_path.with_suffix(f".{target_format}")

        try:
            if target_format == "html":
                converter = MD2HTMLConverter()
            elif target_format == "xml":
                converter = MD2XMLConverter()
            else:
                return ConversionResult(
                    output_path=output_path,
                    success=False,
                    errors=[ErrorDetail(
                        code="UNSUPPORTED_FORMAT",
                        message=f"Format {target_format} not supported by MarkupSpecialist"
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