"""Data Specialist - handles XLSX, CSV, JSON conversions."""

from pathlib import Path
from typing import Optional

from orf.agents.specialists.base import BaseSpecialist
from orf.converters.base import ConversionResult, ErrorDetail
from orf.converters.options import ConverterOptions
from orf.channels.md2xlsx import MD2XLSXConverter
from orf.channels.md2csv import MD2CSVConverter
from orf.channels.md2json import MD2JSONConverter


class DataSpecialist(BaseSpecialist):
    """Handles data format conversions.

    Formats: xlsx, csv, json
    """

    @property
    def supported_formats(self) -> list[str]:
        return ["xlsx", "csv", "json"]

    def convert(
        self,
        input_path: Path,
        output_path: Optional[Path],
        target_format: str,
        **options
    ) -> ConversionResult:
        """Convert MD to data format."""
        if output_path is None:
            output_path = input_path.with_suffix(f".{target_format}")

        try:
            if target_format == "xlsx":
                converter = MD2XLSXConverter()
            elif target_format == "csv":
                converter = MD2CSVConverter()
            elif target_format == "json":
                converter = MD2JSONConverter()
            else:
                return ConversionResult(
                    output_path=output_path,
                    success=False,
                    errors=[ErrorDetail(
                        code="UNSUPPORTED_FORMAT",
                        message=f"Format {target_format} not supported by DataSpecialist"
                    )]
                )

            return converter.convert(input_path, output_path, ConverterOptions(**options))

        except ImportError as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[ErrorDetail(
                    code="MISSING_DEPENDENCY",
                    message=str(e)
                )]
            )
        except Exception as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[ErrorDetail(
                    code="CONVERSION_ERROR",
                    message=str(e)
                )]
            )