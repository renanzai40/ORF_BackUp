"""Markdown to SRT extraction channel for subtitle blocks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger

logger = get_logger("channel.md2srt")

SRT_BLOCK_PATTERN = re.compile(
    r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\Z)",
    re.DOTALL,
)


class MD2SRTConverter(BaseConverter):
    """Extract SRT subtitle blocks from Markdown."""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ):
        super().__init__(manifest, frontmatter)

    @property
    def supported_format(self) -> str:
        return "SRT"

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

        try:
            content = input_path.read_text(encoding="utf-8")
            srt_blocks = self._extract_srt(content)

            if not srt_blocks:
                logger.info("No SRT blocks found, passthrough input")
                output_path.write_text(content, encoding="utf-8")
                return ConversionResult(
                    output_path=output_path,
                    success=True,
                    metadata={"blocks_extracted": 0},
                )

            output_path.write_text(srt_blocks, encoding="utf-8")
            blocks_count = len(re.findall(r"^\d+$", srt_blocks, re.MULTILINE))
            logger.info(f"Extracted {blocks_count} SRT blocks to {output_path}")

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"blocks_extracted": blocks_count},
            )

        except Exception as e:
            logger.error(f"SRT extraction failed: {e}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[str(e)],
            )

    def _extract_srt(self, content: str) -> str:
        """Find and clean SRT blocks in Markdown content."""
        blocks = []
        for match in SRT_BLOCK_PATTERN.finditer(content):
            index = match.group(1)
            start = match.group(2)
            end = match.group(3)
            text = match.group(4).strip()
            cleaned_text = self._clean_subtitle_text(text)
            blocks.append(f"{index}\n{start} --> {end}\n{cleaned_text}")

        return "\n\n".join(blocks) + "\n" if blocks else ""

    def _clean_subtitle_text(self, text: str) -> str:
        """Remove Markdown formatting from subtitle text."""
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"_(.+?)_", r"\1", text)
        text = re.sub(r"~~(.+?)~~", r"\1", text)
        text = re.sub(r"`(.+?)`", r"\1", text)
        return text