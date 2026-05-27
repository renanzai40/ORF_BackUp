"""Markdown to DOCX conversion channel using Pandoc."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger

logger = get_logger("channel.md2docx")


class MD2DOCXConverter(BaseConverter):
    """Markdown to DOCX converter using Pandoc."""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
        reference_docx: Optional[Path | str] = None,
    ) -> None:
        super().__init__(manifest, frontmatter)
        self.reference_docx = Path(reference_docx) if reference_docx else None

    @property
    def supported_format(self) -> str:
        return "DOCX"

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
            "--to", "docx",
        ]

        template = options.get("template") or self.reference_docx
        if template:
            cmd.extend(["--reference-doc", str(template)])

        if options.get("extract_media"):
            cmd.append("--extract-media=.")

        try:
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
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
        """MD2DOCX does not support image injection via paragraph_index.

        Images embedded in MD as base64 data URIs are handled by Pandoc automatically.
        Use Pandoc's --resource-path and --embed-media flag to control media embedding.
        """
        logger.warning(
            "MD2DOCX does not support inject_images via paragraph_index. "
            "Images in MD are handled by Pandoc automatically. "
            "Use --embed-media with Pandoc for inline image embedding."
        )
        return ([], images)
