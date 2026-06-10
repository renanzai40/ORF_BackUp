"""Markdown to XML conversion channel."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from xml.etree.ElementTree import Element, SubElement, tostring

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger
from orf.converters.options import ConverterOptions

logger = get_logger("channel.md2xml")


class MD2XMLConverter(BaseConverter):
    """Markdown to XML converter using stdlib xml.etree.ElementTree."""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ):
        super().__init__(manifest, frontmatter)

    @property
    def supported_format(self) -> str:
        return "XML"

    def validate_input(self, input_path: Path | str) -> bool:
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def _parse_inline(self, text: str) -> str:
        """Parse inline markdown elements to plain text.

        Args:
            text: Text content

        Returns:
            Plain text with inline elements stripped
        """
        # Remove bold/italic markers
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"_(.+?)_", r"\1", text)
        # Remove links, keep text
        text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
        # Remove images
        text = re.sub(r"!\[.*?\]\(.+?\)", "", text)
        # Remove inline code
        text = re.sub(r"`(.+?)`", r"\1", text)
        return text

    def _parse_content(self, content: str) -> list[Element]:
        """Parse markdown content into XML elements.

        Args:
            content: Markdown content

        Returns:
            List of XML elements
        """
        elements: list[Element] = []
        lines = content.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].rstrip("\n")

            # Skip empty lines
            if not line.strip():
                i += 1
                continue

            # Headings
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                level = len(heading_match.group(1))
                text = heading_match.group(2).strip()
                elem = Element(f"h{level}")
                elem.text = self._parse_inline(text)
                elements.append(elem)
                i += 1
                continue

            # Code blocks
            if line.strip().startswith("```"):
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                code_elem = Element("pre")
                code_sub = SubElement(code_elem, "code")
                code_sub.text = "\n".join(code_lines)
                elements.append(code_elem)
                i += 1  # Skip closing ```
                continue

            # Unordered lists
            if re.match(r"^[\-\*\+]\s+", line):
                ul_elem = Element("ul")
                while i < len(lines) and re.match(r"^[\-\*\+]\s+", lines[i]):
                    li_text = re.sub(r"^[\-\*\+]\s+", "", lines[i]).strip()
                    li_elem = SubElement(ul_elem, "li")
                    li_elem.text = self._parse_inline(li_text)
                    i += 1
                elements.append(ul_elem)
                continue

            # Ordered lists
            if re.match(r"^\d+\.\s+", line):
                ol_elem = Element("ol")
                while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                    li_text = re.sub(r"^\d+\.\s+", "", lines[i]).strip()
                    li_elem = SubElement(ol_elem, "li")
                    li_elem.text = self._parse_inline(li_text)
                    i += 1
                elements.append(ol_elem)
                continue

            # Tables
            if line.startswith("|") and line.endswith("|"):
                table_elem = Element("table")
                # Collect table lines
                table_lines = []
                while i < len(lines) and lines[i].startswith("|") and lines[i].endswith("|"):
                    table_lines.append(lines[i])
                    i += 1

                if table_lines:
                    # Skip separator rows and parse data
                    for row_idx, table_row in enumerate(table_lines):
                        # Skip separator like |---|---|
                        if re.match(r"^\|[\s\-:|]+\|$", table_row):
                            continue
                        tr_elem = SubElement(table_elem, "tr")
                        cells = [cell.strip() for cell in table_row[1:-1].split("|")]
                        for cell in cells:
                            td_elem = SubElement(tr_elem, "td")
                            td_elem.text = self._parse_inline(cell)
                    if len(table_elem) > 0:
                        elements.append(table_elem)
                continue

            # Paragraph
            para = Element("p")
            para.text = self._parse_inline(line.strip())
            elements.append(para)
            i += 1

        return elements

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
            elements = self._parse_content(content)

            # Build root element
            root = Element("document")
            for elem in elements:
                root.append(elem)

            # Serialize with proper XML declaration
            xml_str = tostring(root, encoding="unicode")
            output_path.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}', encoding="utf-8")

            logger.debug(f"XML written: {output_path} with {len(elements)} elements")

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"format": "XML", "elements": len(elements)},
            )

        except Exception as e:
            logger.error(f"XML conversion failed: {e}")
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
            "MD2XML does not support inject_images via paragraph_index. "
            "Images in MD are handled by Pandoc automatically. "
            "Use --embed-media with Pandoc for inline image embedding."
        )
        return ([], images)