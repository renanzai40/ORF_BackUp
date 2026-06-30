"""Markdown to XLSX conversion channel."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from openpyxl import Workbook

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger
from orf.converters.options import ConverterOptions

logger = get_logger("channel.md2xlsx")


class MD2XLSXConverter(BaseConverter):
    """Markdown to XLSX converter using openpyxl."""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ) -> None:
        super().__init__(manifest, frontmatter)

    @property
    def supported_format(self) -> str:
        return "XLSX"

    def validate_input(self, input_path: Path | str) -> bool:
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def _parse_table_rows(self, content: str) -> list[list[str]]:
        """Parse markdown table rows from content (single-table view).

        Backward-compat wrapper: returns rows of the FIRST table only.
        For multi-table support, use ``_parse_tables`` which returns
        a list of tables (one per blank-line-separated block).

        Handles both GFM-style tables (with outer | pipes) and
        simplified tables where outer pipes are optional. Also
        tolerates leading/trailing whitespace.
        """
        tables = self._parse_tables(content)
        return tables[0] if tables else []

    def _parse_tables(self, content: str) -> list[list[list[str]]]:
        """Parse markdown into a list of tables.

        A "table boundary" is a blank line OR a non-table line that
        separates two table groups. This means consecutive pipe
        rows (even interleaved with separator lines) form one
        table; a blank line / heading / paragraph ends it.

        Each table is a list of rows, where row 0 is the header
        and rows[1:] are data rows. Separator lines (``|---|---|``)
        are consumed and not included in the output.

        Edge cases:
          - No tables at all: returns ``[]``
          - One table: returns ``[[headers, ...data_rows]]``
          - Tables with only header + separator (no data):
            still returned as a single-row table so the workbook
            preserves the schema
        """
        lines = content.split("\n")
        tables: list[list[list[str]]] = []
        current: list[list[str]] = []
        in_table = False

        def flush() -> None:
            nonlocal current, in_table
            if current:
                tables.append(current)
            current = []
            in_table = False

        for raw_line in lines:
            line = raw_line.strip()
            is_table_row = bool(line) and "|" in line and line.count("|") >= 2
            is_separator = bool(re.match(r"^\|[\s]*:?-+:?[\s]*(?:\|[\s]*:?-+:?[\s]*)+\|$", line)) if is_table_row else False

            if not is_table_row:
                # Blank line / heading / paragraph ends the current table.
                flush()
                continue

            if is_separator:
                # Consume separator; stay in the current table.
                in_table = True
                continue

            # Normalize: add leading/trailing | if missing.
            if not line.startswith("|"):
                line = "|" + line
            if not line.endswith("|"):
                line = line + "|"

            # If we were not already in a table, this row starts a new one.
            if not in_table and not current:
                in_table = True

            cells = [cell.strip() for cell in line[1:-1].split("|")]
            current.append(cells)

        flush()
        return tables

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

        sheet_name = opts.sheet_name

        try:
            content = input_path.read_text(encoding="utf-8")
            # ORG/ORF#34: strip YAML frontmatter before table parsing
            # so frontmatter fields containing '|' don't pollute the
            # table parse. Mirrors md2html.py:61-62.
            from orf.parsers.frontmatter import strip_frontmatter
            content = strip_frontmatter(content)
            tables = self._parse_tables(content)

            if not tables:
                wb = Workbook()
                ws = wb.active
                ws.title = sheet_name
                wb.save(output_path)
                return ConversionResult(
                    output_path=output_path,
                    success=True,
                    metadata={"format": "XLSX", "rows": 0, "sheets": 1},
                )

            wb = Workbook(write_only=True)
            total_data_rows = 0
            for i, table in enumerate(tables):
                # First sheet uses the configured name verbatim; additional
                # sheets get a numeric suffix to keep Excel uniqueness.
                if i == 0:
                    name = sheet_name
                else:
                    name = f"{sheet_name}_{i}"
                ws = wb.create_sheet(title=name)
                headers = table[0]
                ws.append(headers)
                for row in table[1:]:
                    ws.append(row)
                    total_data_rows += 1

            wb.save(output_path)

            logger.debug(
                f"XLSX written: {output_path} with {len(tables)} sheet(s) "
                f"and {total_data_rows} total data row(s)"
            )

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={
                    "format": "XLSX",
                    "rows": total_data_rows,
                    "sheets": len(tables),
                },
            )

        except Exception as e:
            logger.error(f"XLSX conversion failed: {e}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[str(e)],
            )

    def inject_images(
        self,
        skeleton_path: Path | str,
        images: list,
        output_path: Path | str,
    ) -> tuple[list, list]:
        logger.warning(
            "MD2XLSX does not support inject_images via paragraph_index. "
            "Images in MD are handled by Pandoc automatically. "
            "Use --embed-media with Pandoc for inline image embedding."
        )
        return ([], images)
