"""Markdown to CSV conversion channel."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger

logger = get_logger("channel.md2csv")


class MD2CSVConverter(BaseConverter):
    """Markdown to CSV converter using stdlib csv module."""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ):
        super().__init__(manifest, frontmatter)

    @property
    def supported_format(self) -> str:
        return "CSV"

    def validate_input(self, input_path: Path | str) -> bool:
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def _parse_table_rows(self, content: str) -> list[list[str]]:
        """Parse markdown table rows from content.

        Args:
            content: Markdown content

        Returns:
            List of rows, each row is a list of cell values
        """
        lines = content.split("\n")
        rows = []

        for line in lines:
            line = line.strip()
            # Table row must start and end with |
            if not (line.startswith("|") and line.endswith("|")):
                continue

            # Skip separator lines like |---|---|
            if re.match(r"^\|[\s\-:|]+\|$", line):
                continue

            # Strip leading/trailing | and split by |
            cells = [cell.strip() for cell in line[1:-1].split("|")]
            rows.append(cells)

        return rows

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

        delimiter = options.get("delimiter", ",")

        try:
            content = input_path.read_text(encoding="utf-8")
            rows = self._parse_table_rows(content)

            # Handle case with no table
            if not rows:
                # Create empty file
                output_path.write_text("", encoding="utf-8")
                return ConversionResult(
                    output_path=output_path,
                    success=True,
                    metadata={"format": "CSV", "rows": 0},
                )

            # First row is header
            headers = rows[0]
            data_rows = rows[1:] if len(rows) > 1 else []

            # Handle empty table (header only, no data rows)
            if not data_rows:
                output_path.write_text("", encoding="utf-8")
                return ConversionResult(
                    output_path=output_path,
                    success=True,
                    metadata={"format": "CSV", "rows": 0},
                )

            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=delimiter)
                writer.writerow(headers)
                writer.writerows(data_rows)

            logger.debug(f"CSV written: {output_path} with {len(data_rows)} rows")

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"format": "CSV", "rows": len(data_rows)},
            )

        except Exception as e:
            logger.error(f"CSV conversion failed: {e}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[str(e)],
            )