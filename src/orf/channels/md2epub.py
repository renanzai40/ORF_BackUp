"""Markdown to EPUB conversion channel using Pandoc."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger
from orf.converters.options import ConverterOptions

logger = get_logger("channel.md2epub")

_CONVERSION_TIMEOUT = int(os.environ.get("ORF_CONVERSION_TIMEOUT", "300"))


class MD2EPUBConverter(BaseConverter):
    """Markdown to EPUB converter using Pandoc."""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ) -> None:
        super().__init__(manifest, frontmatter)

    @property
    def supported_format(self) -> str:
        return "EPUB"

    def validate_input(self, input_path: Path | str) -> bool:
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def inject_images(
        self,
        skeleton_path: Path | str,
        images: list[Any],
        output_path: Path | str,
    ) -> tuple[list[Any], list[Any]]:
        """EPUB format does not support external image injection.
        Images are embedded by pandoc during conversion.

        Returns empty embedded list and unchanged images list.
        """
        return [], images

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
            "--to", "epub",
        ]

        if opts.css:
            cmd.extend(["--css", opts.css])
        if opts.title:
            cmd.extend(["--metadata", f"title={opts.title}"])
        if opts.author:
            cmd.extend(["--metadata", f"author={opts.author}"])
        if opts.lang:
            cmd.extend(["--metadata", f"lang={opts.lang}"])
        if opts.toc:
            cmd.append("--toc")
        if opts.embed_images:
            cmd.append("--self-contained")

        try:
            logger.info(f"Running: {' '.join(cmd)}")
            cmd[1] = str(input_path.resolve())
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=str(input_path.parent),
                timeout=_CONVERSION_TIMEOUT,
            )

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"tool": "pandoc", "cmd": " ".join(cmd)},
            )

        except subprocess.TimeoutExpired:
            logger.error(f"Pandoc timed out after {_CONVERSION_TIMEOUT}s")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Pandoc timed out after {_CONVERSION_TIMEOUT}s"],
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
