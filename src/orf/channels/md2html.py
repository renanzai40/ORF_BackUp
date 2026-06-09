"""Markdown to HTML conversion channel using Pandoc."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger
from orf.converters.options import ConverterOptions

logger = get_logger("channel.md2html")


class MD2HTMLConverter(BaseConverter):
    """Markdown to HTML converter using Pandoc."""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
        css: Optional[Path | str] = None,
    ) -> None:
        super().__init__(manifest, frontmatter)
        self.css = Path(css) if css else None

    @property
    def supported_format(self) -> str:
        return "HTML"

    def validate_input(self, input_path: Path | str) -> bool:
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        options: ConverterOptions | None = None,
    ) -> ConversionResult:
        input_path = Path(input_path)
        output_path = Path(output_path)
        opts = options or ConverterOptions()

        if not self.validate_input(input_path):
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Invalid input file: {input_path}"],
            )

        cmd = [
            "pandoc",
            str(input_path),
            "-o", str(output_path),
            "--to", "html",
        ]

        css = opts.css or self.css
        if css:
            cmd.extend(["--css", str(css)])

        try:
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=str(input_path.parent),
            )

            logger.debug(f"Pandoc output: {result.stdout}")
            if result.stderr:
                logger.warning(f"Pandoc stderr: {result.stderr}")

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"tool": "pandoc", "cmd": " ".join(cmd)},
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Pandoc failed: {e.stderr}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Pandoc error: {e.stderr}"],
            )
        except FileNotFoundError:
            logger.error("Pandoc not found in PATH")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["Pandoc not installed or not in PATH"],
            )

    def inject_images(
        self,
        skeleton_path: Path | str,
        images: list,
        output_path: Path | str,
    ) -> tuple[list, list]:
        logger.warning(
            "MD2HTML does not support inject_images via paragraph_index. "
            "Images in MD are handled by Pandoc automatically."
        )
        return ([], images)