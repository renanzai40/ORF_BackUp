"""XLIFF to PPTX conversion channel with inline formatting preservation."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from lxml import etree

from orf.converters.base import BaseConverter, ConversionResult
from orf.error_handlers.conversion_error import XLIFFParseError, InlineFormattingError
from orf.logging import get_logger
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.parsers.manifest import Manifest
from orf.skeleton.inline_formatting import (
    InlineElement,
    PPTXInlineApplier,
    XLIFFInlineParser,
)
from orf.skeleton.skeleton_loader import SkeletonLoader

logger = get_logger("channel.xliff2pptx")

# PPTX namespaces
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
A_PREFIX = f"{{{A_NS}}}"

# XLIFF namespace
XLIFF_NS = "urn:oasis:names:tc:xliff:document:2.0"


class XLIFF2PPTXConverter(BaseConverter):
    """XLIFF→PPTX backfill with inline formatting preservation.

    Loads a PPTX skeleton (PPTX is a ZIP), parses translated XLIFF segments,
    and applies translations with inline formatting back into the PPTX slides.
    """

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ):
        """Initialize the XLIFF to PPTX converter.

        Args:
            manifest: OPP manifest.json metadata.
            frontmatter: OL YAML frontmatter metadata.
        """
        super().__init__(manifest, frontmatter)
        self.skeleton_loader = SkeletonLoader()
        self.inline_parser = XLIFFInlineParser()
        self.pptx_applier = PPTXInlineApplier()

    @property
    def supported_format(self) -> str:
        """Return the supported output format."""
        return "PPTX"

    def validate_input(self, input_path: Path | str) -> bool:
        """Validate that the input PPTX skeleton exists.

        Args:
            input_path: Path to the PPTX skeleton file.

        Returns:
            True if valid PPTX file exists.
        """
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".pptx"

    def convert(  # type: ignore[override]
        self,
        pptx_skeleton: Path | str,
        xliff_path: Path | str,
        output_path: Path | str,
        **options: Any,
    ) -> ConversionResult:
        """Convert XLIFF translation back to PPTX with inline formatting.

        Args:
            pptx_skeleton: Path to the PPTX skeleton file (ZIP archive).
            xliff_path: Path to the translated XLIFF file.
            output_path: Path for the output PPTX file.
            **options: Additional options (slide_mapping, etc.)

        Returns:
            ConversionResult with success status and output path.
        """
        pptx_skeleton = Path(pptx_skeleton)
        xliff_path = Path(xliff_path)
        output_path = Path(output_path)

        warnings: list[str] = []

        # 1. Load PPTX skeleton (PPTX is a ZIP)
        try:
            skeleton_data = self._load_pptx_skeleton(pptx_skeleton)
            slide_files = skeleton_data["files"]
            logger.info(f"Loaded PPTX skeleton with {len(slide_files)} files")
        except Exception as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Failed to load PPTX skeleton: {e}"],
            )

        # 2. Parse XLIFF
        try:
            xliff_data = self._parse_xliff(xliff_path)
            logger.info(f"Parsed XLIFF with {len(xliff_data['units'])} translation units")
        except XLIFFParseError as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Failed to parse XLIFF: {e}"],
            )

        modified_slides: dict[str, bytes] = {}
        # 3. Apply translations to slides
        try:
            modified_slides = self._apply_translations_to_slides(
                slide_files,
                xliff_data,
                options,
            )
        except InlineFormattingError as e:
            warnings.append(f"Inline formatting issue: {e}")
            # Continue with best-effort
            modified_slides = slide_files

        # 4. Repack as PPTX
        try:
            self._repack_pptx(output_path, modified_slides, slide_files)
            logger.info(f"Repacked PPTX to {output_path}")
        except Exception as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Failed to repack PPTX: {e}"],
            )

        return ConversionResult(
            output_path=output_path,
            success=True,
            warnings=warnings,
            metadata={
                "slides_processed": len(modified_slides),
                "units_translated": len(xliff_data["units"]),
            },
        )

    def _load_pptx_skeleton(self, pptx_path: Path) -> dict[str, Any]:
        """Load PPTX skeleton file and extract its contents.

        PPTX is a ZIP archive with slides stored in ppt/slides/slideN.xml.

        Args:
            pptx_path: Path to the PPTX file.

        Returns:
            dict with keys: files (dict of filename -> bytes), bytes (bytes)
        """
        files: dict[str, bytes] = {}
        with zipfile.ZipFile(str(pptx_path), "r") as zf:
            for name in zf.namelist():
                files[name] = zf.read(name)

        return {"files": files, "bytes": b""}

    def _parse_xliff(self, xliff_path: Path) -> dict[str, list[dict[str, object]]]:
        """Parse XLIFF file and extract translation units.

        Args:
            xliff_path: Path to the XLIFF file.

        Returns:
            dict with 'units' list of translation units.

        Raises:
            XLIFFParseError: If XLIFF cannot be parsed.
        """
        try:
            tree = etree.parse(str(xliff_path))
            root = tree.getroot()
        except etree.XMLSyntaxError as e:
            raise XLIFFParseError(
                str(xliff_path),
                f"XML syntax error: {e}",
            )

        # Handle XLIFF namespace
        ns = {"xliff": XLIFF_NS}
        units: list[dict[str, object]] = []

        # Find all trans-unit elements
        for unit in root.xpath("//xliff:trans-unit", namespaces=ns):
            unit_id = unit.get("id")
            # Get source and target text
            source_el = unit.find("xliff:source", namespaces=ns)
            target_el = unit.find("xliff:target", namespaces=ns)

            source_text = self._get_element_text(source_el) if source_el is not None else ""
            target_text = self._get_element_text(target_el) if target_el is not None else ""

            # Parse inline elements from target
            inline_elements: list[InlineElement] = []
            if target_text:
                inline_elements = self.inline_parser.parse_from_segment(target_text)

            units.append({
                "id": unit_id,
                "source": source_text,
                "target": target_text,
                "inline_elements": inline_elements,
            })

        return {"units": units}

    def _get_element_text(self, element: etree._Element) -> str:
        """Get concatenated text content from an element.

        Args:
            element: lxml element.

        Returns:
            Text content (may be empty string).
        """
        if element is None:
            return ""
        parts = []
        if element.text:
            parts.append(element.text)
        for child in element:
            parts.append(self._get_element_text(child))
            if child.tail:
                parts.append(child.tail)
        return "".join(parts)

    def _apply_translations_to_slides(
        self,
        slide_files: dict[str, bytes],
        xliff_data: dict[str, list[dict[str, object]]],
        options: dict[str, object],
    ) -> dict[str, bytes]:
        """Apply translation units to PPTX slide XML files.

        Args:
            slide_files: Dict of filename -> file content bytes.
            xliff_data: Parsed XLIFF data with translation units.
            options: Additional options.

        Returns:
            Modified slide files dict.
        """
        modified = dict(slide_files)

        # Build a mapping from source text to target text
        trans_map: dict[str, Any] = {}
        for unit in xliff_data["units"]:
            source = str(unit["source"])
            target = str(unit["target"])
            if source and target:
                trans_map[source] = {
                    "target": target,
                    "inline_elements": unit["inline_elements"],
                }

        # Process each slide file
        for filename in modified:
            if filename.startswith("ppt/slides/slide") and filename.endswith(".xml"):
                xml_content = modified[filename].decode("utf-8")
                modified_xml = self._apply_translation_to_slide_xml(
                    xml_content,
                    trans_map,
                )
                modified[filename] = modified_xml.encode("utf-8")

        return modified

    def _apply_translation_to_slide_xml(
        self,
        xml_content: str,
        trans_map: dict[str, Any],
    ) -> str:
        """Apply translations to a single slide XML content.

        Args:
            xml_content: The slide XML as string.
            trans_map: Mapping from source text to translation data.

        Returns:
            Modified XML content.
        """
        root = etree.fromstring(xml_content.encode("utf-8"))

        # Find all text runs (a:r elements)
        for r_element in root.iter(f"{A_PREFIX}r"):
            # Get text content from this run
            t_elements = list(r_element.iter(f"{A_PREFIX}t"))
            if not t_elements:
                continue

            # Concatenate text from all t elements in this run
            run_text = ""
            for t in t_elements:
                if t.text:
                    run_text += t.text

            # Check if this run's text matches a translation source
            if run_text in trans_map:
                trans_data = trans_map[run_text]
                target_text = trans_data["target"]
                inline_elements = trans_data["inline_elements"]

                # Apply inline formatting
                if inline_elements:
                    formatted_xml = self.pptx_applier.apply_formatting(
                        xml_content,
                        inline_elements,
                        target_text,
                    )
                    if formatted_xml != xml_content:
                        return formatted_xml

                # Simple text replacement in t elements
                if t_elements:
                    for i, t in enumerate(t_elements):
                        t.text = target_text if i == 0 else ""
                    # Clear subsequent t elements' text

        return xml_content

    def _repack_pptx(
        self,
        output_path: Path,
        modified_files: dict[str, bytes],
        original_files: dict[str, bytes],
    ) -> None:
        """Repack modified files into a PPTX archive.

        Args:
            output_path: Path to write the output PPTX.
            modified_files: Dict of modified filename -> content.
            original_files: Original files dict for unchanged entries.
        """
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Write all files, using modified version if available
            for name, data in original_files.items():
                if name in modified_files:
                    zf.writestr(name, modified_files[name])
                else:
                    zf.writestr(name, data)