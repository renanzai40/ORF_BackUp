"""XLIFF→ODF (ODT/ODS) backfill using translate-toolkit."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.logging import get_logger

logger = get_logger("channel.xliff2odf")

# Supported ODF extensions
ODF_EXTENSIONS = {".odt", ".ods", ".odg", ".odi", ".odm", ".odp", ".otp", ".ots", ".ott"}


class XLIFF2ODFConverter(BaseConverter):
    """XLIFF→ODF (ODT/ODS) backfill converter using translate-toolkit.

    Uses the translate-toolkit xliff2odf command to backfill translations
    from an XLIFF file into an ODF skeleton document.

    Example:
        converter = XLIFF2ODFConverter()
        result = converter.convert(
            skeleton_path="original.odt",
            xliff_path="translation.xlf",
            output_path="translated.odt",
        )
    """

    def __init__(
        self,
        manifest: Optional[Any] = None,
        frontmatter: Optional[Any] = None,
    ):
        """Initialize the XLIFF to ODF converter.

        Args:
            manifest: OPP manifest.json metadata
            frontmatter: OL YAML frontmatter metadata
        """
        super().__init__(manifest, frontmatter)

    @property
    def supported_format(self) -> str:
        """Supported output format."""
        return "ODF"

    def validate_input(self, input_skeleton: Path | str) -> bool:
        """Validate input skeleton file.

        Args:
            input_skeleton: Path to the ODF skeleton file.

        Returns:
            True if the file exists and has an ODF extension.
        """
        path = Path(input_skeleton)
        return path.exists() and path.suffix.lower() in ODF_EXTENSIONS

    def convert(
        self,
        skeleton_path: Path | str,
        xliff_path: Path | str,
        output_path: Path | str,
        **options,
    ) -> ConversionResult:
        """Convert XLIFF + skeleton ODF to translated ODF.

        Args:
            skeleton_path: Path to the original ODF skeleton file (ODT/ODS).
            xliff_path: Path to the XLIFF translation file.
            output_path: Path to the output translated ODF file.
            **options: Additional options (source_lang, target_lang, etc.)

        Returns:
            ConversionResult with output path and metadata.
        """
        skeleton_path = Path(skeleton_path)
        xliff_path = Path(xliff_path)
        output_path = Path(output_path)

        warnings: list[str] = []

        # 1. Validate skeleton file
        if not skeleton_path.exists():
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Skeleton file not found: {skeleton_path}"],
            )

        # 2. Validate XLIFF file
        if not xliff_path.exists():
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"XLIFF file not found: {xliff_path}"],
            )

        # 3. Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 4. Run xliff2odf via translate-toolkit
        cmd = [
            "xliff2odf",
            "-t", str(skeleton_path),
            "-i", str(xliff_path),
            "-o", str(output_path),
        ]

        # Add optional exclude patterns if provided
        exclude = options.get("exclude")
        if exclude:
            if isinstance(exclude, str):
                exclude = [exclude]
            for pattern in exclude:
                cmd.extend(["-x", pattern])

        # Add timestamp skip option if requested
        if options.get("timestamp", False):
            cmd.append("-S")

        logger.info(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.debug(f"xliff2odf stdout: {result.stdout}")
            if result.stderr:
                logger.debug(f"xliff2odf stderr: {result.stderr}")

        except subprocess.CalledProcessError as e:
            error_msg = f"xliff2odf failed: {e.stderr}" if e.stderr else f"xliff2odf failed with code {e.returncode}"
            logger.error(error_msg)
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[error_msg],
            )
        except FileNotFoundError:
            error_msg = "xliff2odf command not found. Is translate-toolkit installed?"
            logger.error(error_msg)
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[error_msg],
            )

        # 5. Verify output was created
        if not output_path.exists():
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["xliff2odf completed but output file was not created"],
            )

        return ConversionResult(
            output_path=output_path,
            success=True,
            warnings=warnings if warnings else [],
            metadata={
                "source_format": "XLIFF",
                "target_format": "ODF",
                "skeleton": str(skeleton_path),
                "xliff": str(xliff_path),
                "tool": "translate-toolkit/xliff2odf",
            },
        )