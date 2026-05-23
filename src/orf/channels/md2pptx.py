"""Markdown to PPTX conversion channel using md2pptx CLI."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger

logger = get_logger("channel.md2pptx")


class MD2PPTXConverter(BaseConverter):
    """Markdown to PPTX converter using md2pptx CLI."""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ):
        super().__init__(manifest, frontmatter)

    @property
    def supported_format(self) -> str:
        return "PPTX"

    def validate_input(self, input_path: Path | str) -> bool:
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        **options,
    ) -> ConversionResult:
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not self.validate_input(input_path):
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Invalid input file: {input_path}"],
            )

        cmd = [
            "md2pptx",
            str(input_path),
            "-o", str(output_path),
        ]

        try:
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            logger.debug(f"md2pptx output: {result.stdout}")
            if result.stderr:
                logger.warning(f"md2pptx stderr: {result.stderr}")

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"tool": "md2pptx", "cmd": " ".join(cmd)},
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"md2pptx failed: {e.stderr}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"md2pptx error: {e.stderr}"],
            )
        except FileNotFoundError:
            logger.error("md2pptx not found in PATH")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["md2pptx not installed or not in PATH"],
            )