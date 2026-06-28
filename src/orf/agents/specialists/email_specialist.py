"""Email Specialist - handles EML, MSG conversions."""

from pathlib import Path
from typing import Optional

from orf.agents.specialists.base import BaseSpecialist
from orf.converters.base import ConversionResult, ErrorDetail
from orf.converters.options import ConverterOptions
from orf.channels.md2eml import MD2EMLConverter
from orf.channels.md2msg import MD2MSGConverter
from orf.logging import get_logger

logger = get_logger("agents.email_specialist")


class EmailSpecialist(BaseSpecialist):
    """Handles email format conversions.

    Formats: eml, msg
    """

    @property
    def supported_formats(self) -> list[str]:
        return ["eml", "msg"]

    def convert(
        self,
        input_path: Path,
        output_path: Optional[Path],
        target_format: str,
        **options
    ) -> ConversionResult:
        """Convert MD to email format."""
        if output_path is None:
            output_path = input_path.with_suffix(f".{target_format}")

        try:
            if target_format == "eml":
                converter = MD2EMLConverter()
            elif target_format == "msg":
                converter = MD2MSGConverter()
            else:
                return ConversionResult(
                    output_path=output_path,
                    success=False,
                    errors=[ErrorDetail(
                        code="UNSUPPORTED_FORMAT",
                        message=f"Format {target_format} not supported by EmailSpecialist"
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
            logger.warning("EmailSpecialist conversion failed: %s", e, exc_info=True)
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[ErrorDetail(
                    code="CONVERSION_ERROR",
                    message=str(e)
                )]
            )