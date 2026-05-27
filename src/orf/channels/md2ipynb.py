"""Markdown to Jupyter Notebook conversion channel."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

import nbformat
from nbformat.v4 import new_notebook, new_code_cell, new_markdown_cell

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger

logger = get_logger("channel.md2ipynb")


class MD2IPYNBConverter(BaseConverter):
    """Markdown to Jupyter Notebook converter using nbformat."""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ):
        super().__init__(manifest, frontmatter)

    @property
    def supported_format(self) -> str:
        return "IPYNB"

    def validate_input(self, input_path: Path | str) -> bool:
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def _parse_markdown(self, content: str) -> list[Dict[str, Any]]:
        """Parse markdown content into notebook cells.

        Args:
            content: Markdown content

        Returns:
            List of cell dictionaries with 'type' and 'content' keys
        """
        cells = []
        # Regex for fenced code blocks: ```language\n...```
        code_block_pattern = re.compile(
            r"```(\w*)\n(.*?)```",
            re.DOTALL | re.MULTILINE,
        )

        last_end = 0
        for match in code_block_pattern.finditer(content):
            # Text before code block becomes markdown cell
            before = content[last_end : match.start()].strip()
            if before:
                cells.append({"type": "markdown", "content": before})

            # Code block becomes code cell
            language = match.group(1) or "python"
            code = match.group(2).rstrip("\n")
            cells.append({"type": "code", "content": code, "language": language})

            last_end = match.end()

        # Remaining content after last code block
        remaining = content[last_end:].strip()
        if remaining:
            cells.append({"type": "markdown", "content": remaining})

        return cells

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

        kernel_name = options.get("kernel", "python3")

        try:
            content = input_path.read_text(encoding="utf-8")
            parsed_cells = self._parse_markdown(content)

            if not parsed_cells:
                # Empty notebook
                nb = new_notebook()
            else:
                nb_cells = []
                for cell_data in parsed_cells:
                    if cell_data["type"] == "markdown":
                        nb_cells.append(
                            new_markdown_cell(cell_data["content"])
                        )
                    else:  # code
                        code_cell = new_code_cell(cell_data["content"])
                        # Set language metadata
                        language = cell_data.get("language", "python")
                        code_cell.metadata = {
                            "language": language.capitalize(),
                        }
                        nb_cells.append(code_cell)

                nb = new_notebook(cells=nb_cells)

            # Set kernel metadata
            nb.metadata = {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": kernel_name,
                },
                "language_info": {
                    "name": "python",
                    "version": "3.0.0",
                },
            }

            # Write notebook
            nbformat.write(nb, output_path)

            code_cell_count = sum(
                1 for c in parsed_cells if c["type"] == "code"
            )
            markdown_cell_count = sum(
                1 for c in parsed_cells if c["type"] == "markdown"
            )

            logger.debug(
                f"IPYNB written: {output_path} "
                f"({code_cell_count} code, {markdown_cell_count} markdown)"
            )

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={
                    "format": "IPYNB",
                    "code_cells": code_cell_count,
                    "markdown_cells": markdown_cell_count,
                },
            )

        except Exception as e:
            logger.error(f"IPYNB conversion failed: {e}")
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
            "MD2IPYNB does not support inject_images via paragraph_index. "
            "Images in MD are handled by Pandoc automatically. "
            "Use --embed-media with Pandoc for inline image embedding."
        )
        return ([], images)