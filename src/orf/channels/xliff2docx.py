"""XLIFF→DOCX backfill with inline formatting preservation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from lxml import etree

from orf.converters.base import BaseConverter, ConversionResult
from orf.error_handlers.conversion_error import XLIFFParseError
from orf.logging import get_logger
from orf.skeleton.inline_formatting import (
    DOCXInlineApplier,
    InlineElement,
    XLIFFInlineParser,
)
from orf.skeleton.skeleton_loader import SkeletonLoader

logger = get_logger("channel.xliff2docx")

# XLIFF namespaces
XLIFF_NS = "urn:oasis:names:tc:xliff:document:1.2"
XLIFF_NS_MAP = {"xliff": XLIFF_NS}


@dataclass
class XLIFFTransUnitData:
    """Minimal trans-unit data extracted from XLIFF."""

    id: str
    source: str
    target: Optional[str] = None
    segments: list[str] | None = None


@dataclass
class InlineElementData:
    """Inline element data for backfill."""

    id: str
    type: str
    begin_pos: int
    end_pos: int
    text_covered: Optional[str] = None


class XLIFF2DOCXConverter(BaseConverter):
    """XLIFF→DOCX backfill with inline formatting preservation.

    Loads a DOCX skeleton, parses XLIFF translation units, and backfills
    the target translations with inline formatting preserved.
    """

    def __init__(
        self,
        manifest: Optional[Any] = None,
        frontmatter: Optional[Any] = None,
    ):
        super().__init__(manifest, frontmatter)
        self.skeleton_loader = SkeletonLoader()
        self.inline_parser = XLIFFInlineParser()
        self.docx_applier = DOCXInlineApplier()

    @property
    def supported_format(self) -> str:
        return "DOCX"

    def validate_input(self, input_skeleton: Path | str) -> bool:
        """Validate input skeleton file."""
        path = Path(input_skeleton)
        return path.exists() and path.suffix.lower() in (".docx", ".zip")

    def _parse_xliff(self, xliff_path: Path | str) -> list[dict[str, Any]]:
        """Parse XLIFF file and extract trans-units.

        Args:
            xliff_path: Path to XLIFF file.

        Returns:
            List of trans-unit dictionaries with id, source, target.

        Raises:
            XLIFFParseError: If XLIFF cannot be parsed.
        """
        path = Path(xliff_path)
        if not path.exists():
            raise XLIFFParseError(
                str(path),
                f"File not found: {path}",
            )

        try:
            tree = etree.parse(str(path), etree.XMLParser(recover=True))
            root = tree.getroot()
        except etree.XMLSyntaxError as e:
            raise XLIFFParseError(str(path), f"XML parse error: {e}")

        if root is None:
            raise XLIFFParseError(str(path), "Failed to parse XML - no root element")

        trans_units: list[dict[str, Any]] = []

        # Handle both xliff 1.2 and 2.0 formats
        # xliff 1.2: /xliff/file/body/trans-unit
        # xliff 2.0: /xliff/ns:file/ns:unit

        # Try xliff 1.2 first
        for tu in root.xpath(
            "//xliff:trans-unit",
            namespaces=XLIFF_NS_MAP,
        ):
            tu_id = tu.get("id")
            if not tu_id:
                continue

            source_el = tu.find("xliff:source", namespaces=XLIFF_NS_MAP)
            target_el = tu.find("xliff:target", namespaces=XLIFF_NS_MAP)

            source_text = (
                "".join(source_el.itertext()) if source_el is not None else ""
            )
            target_text = (
                "".join(target_el.itertext()) if target_el is not None else ""
            )

            # Extract inline elements from source
            source_xml = etree.tostring(source_el, encoding="unicode") if source_el is not None else ""
            inline_elements = self._extract_inline_elements(source_xml)

            trans_units.append({
                "id": tu_id,
                "source": source_text,
                "target": target_text,
                "inline_elements": inline_elements,
            })

        # Try xliff 2.0 unit elements if no 1.2 trans-units found
        if not trans_units:
            for unit in root.xpath(
                "//xliff:unit",
                namespaces=XLIFF_NS_MAP,
            ):
                unit_id = unit.get("id")
                if not unit_id:
                    continue

                # xliff 2.0 uses segement elements inside unit
                segments = unit.findall("xliff:segment", namespaces=XLIFF_NS_MAP)
                if segments:
                    for seg in segments:
                        seg_id = seg.get("id", unit_id)
                        source_el = seg.find("xliff:source", namespaces=XLIFF_NS_MAP)
                        target_el = seg.find("xliff:target", namespaces=XLIFF_NS_MAP)

                        source_text = (
                            "".join(source_el.itertext()) if source_el is not None else ""
                        )
                        target_text = (
                            "".join(target_el.itertext()) if target_el is not None else ""
                        )

                        source_xml = etree.tostring(source_el, encoding="unicode") if source_el is not None else ""
                        inline_elements = self._extract_inline_elements(source_xml)

                        trans_units.append({
                            "id": seg_id,
                            "source": source_text,
                            "target": target_text,
                            "inline_elements": inline_elements,
                        })
                else:
                    # No segments, treat whole unit as one trans-unit
                    source_el = unit.find("xliff:source", namespaces=XLIFF_NS_MAP)
                    target_el = unit.find("xliff:target", namespaces=XLIFF_NS_MAP)

                    source_text = (
                        "".join(source_el.itertext()) if source_el is not None else ""
                    )
                    target_text = (
                        "".join(target_el.itertext()) if target_el is not None else ""
                    )

                    source_xml = etree.tostring(source_el, encoding="unicode") if source_el is not None else ""
                    inline_elements = self._extract_inline_elements(source_xml)

                    trans_units.append({
                        "id": unit_id,
                        "source": source_text,
                        "target": target_text,
                        "inline_elements": inline_elements,
                    })

        logger.debug(f"Parsed {len(trans_units)} trans-units from {path}")
        return trans_units

    def _extract_inline_elements(self, source_xml: str) -> list[InlineElement]:
        """Extract inline elements from XLIFF source XML.

        Args:
            source_xml: Source element XML as string.

        Returns:
            List of InlineElement objects.
        """
        if not source_xml:
            return []

        # Use the inline parser to extract elements from the XML
        try:
            elements = self.inline_parser.parse_source(source_xml)
            # Map to text positions
            mapped = self.inline_parser.map_elements_to_positions(source_xml, elements)
            return mapped
        except Exception as e:
            logger.warning(f"Failed to parse inline elements: {e}")
            return []

    def convert(  # type: ignore[no-untyped-def]
        self,
        input_skeleton: Path | str,
        xliff_path: Path | str,
        output_path: Path | str,
        **options: Any,
    ) -> ConversionResult:
        """Convert XLIFF + skeleton to DOCX.

        Args:
            input_skeleton: Path to skeleton DOCX file.
            xliff_path: Path to XLIFF translation file.
            output_path: Path to output DOCX file.
            **options: Additional options (segment_mapping, etc.)

        Returns:
            ConversionResult with output path and metadata.
        """
        input_skeleton = Path(input_skeleton)
        xliff_path = Path(xliff_path)
        output_path = Path(output_path)

        warnings: list[str] = []
        inline_elements_applied = 0

        # 1. Load skeleton (original DOCX ZIP)
        try:
            skeleton_data = self.skeleton_loader.load_skeleton(str(input_skeleton))
            document_xml = skeleton_data["xml"]
        except Exception as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Failed to load skeleton: {e}"],
            )

        # 2. Parse XLIFF
        try:
            trans_units = self._parse_xliff(xliff_path)
        except XLIFFParseError as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"XLIFF parse error: {e}"],
            )

        if not trans_units:
            warnings.append("No trans-units found in XLIFF file")

        # 3. For each trans-unit, backfill target text
        for tu in trans_units:
            tu_id = tu["id"]
            target_text = tu.get("target", "")
            inline_elements = tu.get("inline_elements", [])

            if not target_text:
                # Skip empty translations
                continue

            try:
                # Find the paragraph in document.xml that matches source text
                # and backfill with target text + inline formatting
                success = self._backfill_translation(
                    document_xml,
                    tu["source"],
                    target_text,
                    inline_elements,
                )
                if success:
                    inline_elements_applied += len(inline_elements)
            except Exception as e:
                logger.warning(f"Failed to backfill trans-unit {tu_id}: {e}")
                warnings.append(f"Failed to backfill unit {tu_id}: {e}")

        # 4. Repack as DOCX
        try:
            self.skeleton_loader.repack_docx(str(output_path), document_xml)
        except Exception as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Failed to repack DOCX: {e}"],
            )

        return ConversionResult(
            output_path=output_path,
            success=True,
            warnings=warnings if warnings else [],
            metadata={
                "inline_elements_applied": inline_elements_applied,
                "trans_units_processed": len(trans_units),
            },
        )

    def _backfill_translation(
        self,
        document_xml: str,
        source_text: str,
        target_text: str,
        inline_elements: list[InlineElement],
    ) -> bool:
        """Backfill a single translation into document XML.

        Args:
            document_xml: The document.xml content.
            source_text: Original source text (for finding location).
            target_text: Translated target text.
            inline_elements: Inline formatting elements.

        Returns:
            True if backfill was successful.
        """
        if not source_text and not target_text:
            return False

        root = etree.fromstring(document_xml.encode("utf-8"))

        # Find all text runs containing the source text
        W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

        found = False
        for t_elem in root.xpath(f"//{{{W_NS}}}t"):
            if t_elem.text and source_text in t_elem.text:
                found = True
                # Replace text with target text
                t_elem.text = target_text

                # Apply inline formatting if any
                if inline_elements:
                    try:
                        self._apply_inline_formatting_to_run(
                            t_elem,
                            inline_elements,
                            target_text,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to apply inline formatting: {e}")

        if not found:
            # Fallback: try plain text backfill for paragraph
            # Find paragraph containing source text
            paragraphs = root.xpath(f"//{{{W_NS}}}p", namespaces={"w": W_NS})
            for p in paragraphs:
                text_content = "".join(
                    t.text for t in p.xpath(f".//{{{W_NS}}}t") if t.text
                )
                if source_text in text_content:
                    # Backfill plain text
                    for t in p.xpath(f".//{{{W_NS}}}t"):
                        if t.text and source_text in t.text:
                            t.text = target_text
                            found = True
                            break
                if found:
                    break

        if found:
            # Update document_xml with modified content
            new_xml = etree.tostring(root, encoding="unicode", xml_declaration=True)
            document_xml = new_xml

        return found

    def _apply_inline_formatting_to_run(
        self,
        t_elem: etree._Element,
        inline_elements: list[InlineElement],
        target_text: str,
    ) -> None:
        """Apply inline formatting to a text run element.

        Args:
            t_elem: The w:t element to apply formatting to.
            inline_elements: List of inline elements to apply.
            target_text: The target text for formatting.
        """
        # Get parent w:r element
        parent = t_elem.getparent()
        if parent is None:
            return

        r_parent = parent.getparent()
        if r_parent is None:
            r_parent = parent

        # Insert rPr (run properties) before the w:t element
        rpr = etree.SubElement(r_parent, f"{{{self.docx_applier.W_NS}}}rPr")

        for elem in inline_elements:
            if elem.type == "close":
                continue

            tag_name = self.docx_applier.TYPE_TO_TAG.get(elem.type.lower(), elem.type)
            if tag_name:
                prop_elem = etree.SubElement(rpr, f"{{{self.docx_applier.W_NS}}}{tag_name}")

                # Handle special properties like underline with val attribute
                if elem.type.lower() in ("underline", "double-underline", "single-underline"):
                    val = "single" if elem.type.lower() == "underline" else "double"
                    prop_elem.set(f"{{{self.docx_applier.W_NS}}}val", val)