"""Markdown to JSON conversion channel."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger
from orf.converters.options import ConverterOptions

logger = get_logger("channel.md2json")

JSON_BLOCK_PATTERN = re.compile(r"```json\s*(.*?)\s*(?:```|$)", re.DOTALL)


class MD2JSONConverter(BaseConverter):
    """Markdown to JSON converter."""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ):
        super().__init__(manifest, frontmatter)

    @property
    def supported_format(self) -> str:
        return "JSON"

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

        if not self.validate_input(input_path):
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Invalid input file: {input_path}"],
            )

        try:
            content = input_path.read_text(encoding="utf-8")
        except Exception as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Failed to read input file: {e}"],
            )

        match = JSON_BLOCK_PATTERN.search(content)
        if not match:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["No JSON code block found in Markdown"],
            )

        json_str = match.group(1)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Invalid JSON syntax: {e}"],
            )

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Failed to write output file: {e}"],
            )

        return ConversionResult(
            output_path=output_path,
            success=True,
            metadata={"source_format": "MD"},
        )

    def inject_images(
        self,
        skeleton_path: Path | str,
        images: list,
        output_path: Path | str,
    ) -> tuple[list, list]:
        logger.warning(
            "MD2JSON does not support inject_images via paragraph_index. "
            "Images in MD are handled by Pandoc automatically."
        )
        return ([], images)