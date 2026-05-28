"""Markdown to EPUB conversion channel using Pandoc."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger

logger = get_logger("channel.md2epub")


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

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        **options: Any,
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
            "pandoc",
            str(input_path),
            "-o", str(output_path),
            "--to", "epub",
        ]

        if options.get("title"):
            cmd.extend(["--metadata", f"title={options['title']}"])
        if options.get("author"):
            cmd.extend(["--metadata", f"author={options['author']}"])
        if options.get("lang"):
            cmd.extend(["--metadata", f"lang={options['lang']}"])
        if options.get("toc"):
            cmd.append("--toc")
        if options.get("embed_images"):
            cmd.append("--self-contained")

        try:
            logger.info(f"Running: {' '.join(cmd)}")
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=str(input_path.parent),
            )

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
