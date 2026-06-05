"""XLIFF to PPTX conversion channel with inline formatting preservation."""

from __future__ import annotations

import base64
import hashlib
import zipfile
from pathlib import Path
from typing import Any, Optional

from lxml import etree

from orf.converters.base import BaseConverter, ConversionResult
from orf.error_handlers.conversion_error import XLIFFParseError, InlineFormattingError
from orf.logging import get_logger
from orf.mcp.schemas import ImagePlacement
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
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
P_PREFIX = f"{{{P_NS}}}"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

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

    def inject_images(
        self,
        skeleton_path: Path | str,
        images: list[ImagePlacement],
        output_path: Path | str,
    ) -> tuple[list[ImagePlacement], list[ImagePlacement]]:
        """Inject images into PPTX skeleton at specified slide positions.

        Args:
            skeleton_path: Path to skeleton PPTX file.
            images: List of ImagePlacement objects from OPP.
            output_path: Path to write the output PPTX.

        Returns:
            Tuple of (injected_images, orphaned_images).
        """
        skeleton_path = Path(skeleton_path)
        output_path = Path(output_path)

        orphaned: list[ImagePlacement] = []
        injected: list[ImagePlacement] = []

        positioned = [img for img in images if img.slide_index is not None]
        unpositioned = [img for img in images if img.slide_index is None]

        if unpositioned:
            for img in unpositioned:
                logger.warning(
                    "Image has no slide_index, appending to end: mime_type=%s",
                    img.mime_type,
                )
            orphaned.extend(unpositioned)

        if not positioned:
            if images:
                with zipfile.ZipFile(skeleton_path, "r") as zf_in:
                    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf_out:
                        for item in zf_in.namelist():
                            zf_out.writestr(item, zf_in.read(item))
            return (injected, orphaned)

        try:
            skeleton_data = self._load_pptx_skeleton(skeleton_path)
            files = skeleton_data["files"]
        except Exception as e:
            logger.error("Failed to load PPTX skeleton for image injection: %s", e)
            orphaned.extend(images)
            return (injected, orphaned)

        img_by_slide: dict[int, list[ImagePlacement]] = {}
        for img in positioned:
            idx = img.slide_index
            assert idx is not None, "positioned images must have slide_index"
            if idx not in img_by_slide:
                img_by_slide[idx] = []
            img_by_slide[idx].append(img)

        slide_numbers = sorted(img_by_slide.keys())

        for slide_num in slide_numbers:
            slide_file_name = f"ppt/slides/slide{slide_num + 1}.xml"
            if slide_file_name not in files:
                logger.warning(
                    "Slide %d not found in skeleton, skipping images",
                    slide_num,
                )
                orphaned.extend(img_by_slide[slide_num])
                continue

            slide_xml = files[slide_file_name].decode("utf-8")

            for i, img in enumerate(img_by_slide[slide_num]):
                try:
                    img_bytes = self._get_image_bytes(img)
                    rId = self._add_image_to_pptx(img_bytes, img.mime_type, files, slide_num)
                    width, height = self._get_image_dimensions(img, img_bytes)
                    pic_xml = self._create_pic_xml(rId, width, height, slide_num)
                    pic_elem = etree.fromstring(pic_xml)

                    root = etree.fromstring(slide_xml.encode("utf-8"))
                    sp_tree = root.find(f".//{P_PREFIX}spTree")
                    if sp_tree is not None:
                        sp_tree.append(pic_elem)
                        slide_xml = etree.tostring(root, encoding="unicode", xml_declaration=True)
                        files[slide_file_name] = slide_xml.encode("utf-8")
                        injected.append(img)
                        logger.debug(
                            "Injected image at slide %d: rId=%s, mime=%s",
                            slide_num,
                            rId,
                            img.mime_type,
                        )
                    else:
                        orphaned.append(img)
                except Exception as e:
                    logger.error("Failed to inject image into slide %d: %s", slide_num, e)
                    orphaned.append(img)

        self._repack_pptx(output_path, files, files)

        if orphaned:
            logger.warning(
                "%d images could not be positioned and were not injected",
                len(orphaned),
            )

        return (injected, orphaned)

    def _get_image_bytes(self, img: ImagePlacement) -> bytes:
        if img.data_base64:
            return base64.b64decode(img.data_base64)
        if img.file_path:
            # C4 fix (defense in depth): validate file_path before reading.
            from orf.mcp.security import PathValidator
            valid, err = PathValidator.validate(img.file_path)
            if not valid:
                raise ValueError(f"file_path rejected: {err}")
            return Path(img.file_path).read_bytes()
        raise ValueError("ImagePlacement must have data_base64 or file_path")

    def _get_image_dimensions(
        self, img: ImagePlacement, img_bytes: bytes
    ) -> tuple[int, int]:
        if img.width is not None and img.height is not None:
            return (img.width, img.height)

        try:
            from PIL import Image
            from io import BytesIO

            img_obj = Image.open(BytesIO(img_bytes))
            w, h = img_obj.size
            return (w, h)
        except Exception:
            return (914400, 685800)

    def _add_image_to_pptx(
        self,
        img_bytes: bytes,
        mime_type: str,
        files: dict[str, bytes],
        slide_num: int,
    ) -> str:
        ext_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "image/bmp": ".bmp",
            "image/webp": ".webp",
        }
        ext = ext_map.get(mime_type, ".png")
        md5_hash = hashlib.md5(img_bytes).hexdigest()
        dedup_name = f"image_{md5_hash[:8]}{ext}"
        media_name = f"ppt/media/{dedup_name}"

        existing_name = None
        for name, data in files.items():
            if name.startswith("ppt/media/") and data == img_bytes:
                existing_name = name
                break

        if existing_name:
            rid = existing_name.replace("ppt/media/", "rId")
            return rid

        files[media_name] = img_bytes

        slide_rels_name = f"ppt/slides/_rels/slide{slide_num + 1}.xml.rels"
        if slide_rels_name not in files:
            rels_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/slide0.png"/></Relationships>'
            files[slide_rels_name] = rels_xml.encode("utf-8")

        rels_xml = files[slide_rels_name].decode("utf-8")
        root = etree.fromstring(rels_xml.encode("utf-8"))

        max_rid = 0
        for rel in root.xpath("//*"):
            rid = rel.get("Id", "")
            if rid.startswith("rId"):
                try:
                    num = int(rid[3:])
                    if num > max_rid:
                        max_rid = num
                except ValueError:
                    pass

        new_rid = f"rId{max_rid + 1}"
        rels_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        new_rel = etree.SubElement(root, f"{{{rels_ns}}}Relationship")
        new_rel.set("Id", new_rid)
        new_rel.set(
            "Type",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
        )
        new_rel.set("Target", f"media/{dedup_name}")

        files[slide_rels_name] = etree.tostring(root, encoding="unicode").encode("utf-8")

        return new_rid

    def _create_pic_xml(
        self,
        rId: str,
        cx: int,
        cy: int,
        slide_num: int,
    ) -> str:
        x = 457200
        y = 457200
        pic = f'''<p:pic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:nvPicPr>
    <p:cNvPr id="1" name="Picture" descr="image"/>
    <p:cNvPicPr>
      <a:picLocks noChangeAspect="1"/>
    </p:cNvPicPr>
    <p:nvPr/>
  </p:nvPicPr>
  <p:blipFill>
    <a:blip r:embed="{rId}"/>
    <a:stretch>
      <a:fillRect/>
    </a:stretch>
  </p:blipFill>
  <p:spPr>
    <a:xfrm>
      <a:off x="{x}" y="{y}"/>
      <a:ext cx="{cx}" cy="{cy}"/>
    </a:xfrm>
    <a:prstGeom prst="rect">
      <a:avLst/>
    </a:prstGeom>
  </p:spPr>
</p:pic>'''
        return pic