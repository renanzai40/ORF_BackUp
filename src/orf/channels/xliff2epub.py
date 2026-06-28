"""XLIFF→EPUB backfill converter with inline formatting preservation.

Applies translated XLIFF content to EPUB skeleton, preserving inline formatting
from XLIFF <bx>/<ex> tags converted to HTML <strong>/<em> tags.
"""

from __future__ import annotations

import base64
import hashlib
import zipfile
from pathlib import Path
from typing import Any, Optional

from bs4 import BeautifulSoup
from lxml import etree

from orf.converters.base import BaseConverter, ConversionResult
from orf.mcp.schemas import ImagePlacement
from orf.skeleton.inline_formatting import XLIFFInlineParser, EPUBHTMLInlineApplier
from orf.skeleton.skeleton_loader import SkeletonLoader
from orf.error_handlers.conversion_error import XLIFFParseError, InlineFormattingError
from orf.logging import get_logger
from orf.converters.options import ConverterOptions

logger = get_logger("channel.xliff2epub")

# EPUB internal paths
EPUB_CONTENT_PATHS = ["EPUB/", "OEBPS/"]  # Common EPUB content directories
XHTML_EXTENSIONS = (".xhtml", ".html", ".htm")

# XLIFF namespaces (mirror xliff2docx.py T1 pattern)
XLIFF_NS_1_2 = "urn:oasis:names:tc:xliff:document:1.2"
XLIFF_NS_1_1 = "urn:oasis:names:tc:xliff:document:1.1"
XLIFF_NS_2_0 = "urn:oasis:names:tc:xliff:document:2.0"
XLIFF_NS_MAP_1_2 = {"xliff": XLIFF_NS_1_2}
XLIFF_NS_MAP_1_1 = {"xliff": XLIFF_NS_1_1}
XLIFF_NS_MAP_2_0 = {"xliff": XLIFF_NS_2_0}


class XLIFF2EPUBConverter(BaseConverter):
    """XLIFF→EPUB backfill with inline formatting preservation.

    Loads an EPUB skeleton (ZIP), applies translated XLIFF content to each
    XHTML chapter, and repacks the EPUB with inline formatting converted to HTML.
    """

    def __init__(self, manifest: Optional[Any] = None, frontmatter: Optional[Any] = None) -> None:
        super().__init__(manifest, frontmatter)
        self.inline_parser = XLIFFInlineParser()
        self.epub_applier = EPUBHTMLInlineApplier()

    @property
    def supported_format(self) -> str:
        return "EPUB"

    def validate_input(self, input_path: Path | str) -> bool:
        """Validate input EPUB skeleton path."""
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() in (".epub", ".zip")

    def convert(  # type: ignore[override]
        self,
        input_path: Path | str,
        xliff_path: Path | str,
        output_path: Path | str,
        options: ConverterOptions | None = None,
    ) -> ConversionResult:
        """Apply XLIFF translations to EPUB skeleton.

        Args:
            input_path: Path to EPUB skeleton file.
            xliff_path: Path to the XLIFF translation file.
            output_path: Path to write the output EPUB.
            options: Converter options (preserve_styles, etc.).

        Returns:
            ConversionResult with output path and status.
        """
        epub_skeleton = Path(input_path)
        xliff_path = Path(xliff_path)
        output_path = Path(output_path)

        # 1. Validate EPUB skeleton
        if not epub_skeleton.exists():
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"EPUB skeleton not found: {epub_skeleton}"],
            )

        # 2. Validate XLIFF file
        if not xliff_path.exists():
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"XLIFF file not found: {xliff_path}"],
            )

        try:
            # 3. Parse XLIFF to extract segments
            xliff_segments = self._parse_xliff(xliff_path)
            logger.info(f"Parsed {len(xliff_segments)} segments from XLIFF")

            # 4. Load EPUB skeleton (ZIP contents)
            epub_files = self._load_epub_skeleton(epub_skeleton)
            if not epub_files:
                return ConversionResult(
                    output_path=output_path,
                    success=False,
                    errors=["EPUB skeleton is empty or invalid"],
                )

            # 5. Apply translations to XHTML content
            modified_files = self._apply_translations_to_epub(
                epub_files, xliff_segments, options
            )

            # 6. Repack as EPUB
            self._repack_epub(modified_files, output_path)

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={
                    "segments_applied": len(xliff_segments),
                    "files_modified": len(modified_files),
                },
            )

        except XLIFFParseError as e:
            logger.error(f"XLIFF parse error: {e}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[str(e)],
            )
        except InlineFormattingError as e:
            logger.error(f"Inline formatting error: {e}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[str(e)],
            )
        except Exception as e:
            logger.error(f"Unexpected error during conversion: {e}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Conversion failed: {e}"],
            )

    def _parse_xliff(self, xliff_path: Path) -> dict[str, str]:
        """Parse XLIFF file and extract target segments.

        Uses lxml.etree rather than regex because regex silently breaks
        on inline tags (``<g>``, ``<bx>``, ``<ex>``, ``<ph>``, ``<it>``),
        CDATA sections, and multi-line ``<target>`` bodies.
        ``target.itertext()`` flattens the tree, dropping markup while
        preserving inter-element whitespace.

        Args:
            xliff_path: Path to XLIFF file.

        Returns:
            Dict mapping segment id to translated target text.

        Raises:
            XLIFFParseError: If XLIFF cannot be parsed.
        """
        try:
            with open(xliff_path, "rb") as f:
                content = f.read()
        except Exception as e:
            logger.debug("Failed to read XLIFF file: %s", e, exc_info=True)
            raise XLIFFParseError(str(xliff_path), f"Cannot read file: {e}")

        try:
            root = etree.fromstring(content)
        except etree.XMLSyntaxError as e:
            raise XLIFFParseError(str(xliff_path), f"XML parse error: {e}")

        if root is None:
            raise XLIFFParseError(str(xliff_path), "Failed to parse XML - no root element")

        segments: dict[str, str] = {}

        def _extract_target_text(target_el: etree._Element | None) -> str:
            if target_el is None:
                return ""
            return "".join(target_el.itertext())

        for tu in root.xpath("//xliff:trans-unit", namespaces=XLIFF_NS_MAP_1_2):
            tu_id = tu.get("id")
            if not tu_id:
                continue
            target_el = tu.find("xliff:target", namespaces=XLIFF_NS_MAP_1_2)
            segments[tu_id] = _extract_target_text(target_el)

        if not segments:
            for tu in root.xpath("//xliff:trans-unit", namespaces=XLIFF_NS_MAP_1_1):
                tu_id = tu.get("id")
                if not tu_id:
                    continue
                target_el = tu.find("xliff:target", namespaces=XLIFF_NS_MAP_1_1)
                segments[tu_id] = _extract_target_text(target_el)

        if not segments:
            for unit in root.xpath("//xliff:unit", namespaces=XLIFF_NS_MAP_2_0):
                unit_id = unit.get("id")
                if not unit_id:
                    continue
                seg_elements = unit.findall("xliff:segment", namespaces=XLIFF_NS_MAP_2_0)
                if seg_elements:
                    for seg in seg_elements:
                        seg_id = seg.get("id", unit_id)
                        target_el = seg.find("xliff:target", namespaces=XLIFF_NS_MAP_2_0)
                        segments[seg_id] = _extract_target_text(target_el)
                else:
                    target_el = unit.find("xliff:target", namespaces=XLIFF_NS_MAP_2_0)
                    segments[unit_id] = _extract_target_text(target_el)

        if not segments:
            logger.warning(f"No segments found in XLIFF: {xliff_path}")

        return segments

    def _load_epub_skeleton(self, epub_path: Path) -> dict[str, bytes]:
        """Load EPUB skeleton ZIP contents.

        Args:
            epub_path: Path to EPUB file.

        Returns:
            Dict mapping file paths to their byte contents.
        """
        files = {}

        with zipfile.ZipFile(epub_path, "r") as zf:
            for name in zf.namelist():
                SkeletonLoader._validate_zip_entry_name(name)
            for name in zf.namelist():
                files[name] = zf.read(name)

        return files

    def _apply_translations_to_epub(
        self,
        epub_files: dict[str, bytes],
        xliff_segments: dict[str, str],
        options: ConverterOptions | None = None,
    ) -> dict[str, bytes]:
        """Apply XLIFF translations to EPUB XHTML files.

        Args:
            epub_files: Dict of EPUB file paths to contents.
            xliff_segments: Dict of segment IDs to translated text.
            options: Additional options.

        Returns:
            Dict of modified file paths to contents.
        """
        modified = dict(epub_files)

        # Find XHTML files to process
        xhtml_files = self._find_xhtml_files(epub_files)

        for file_path, content in xhtml_files.items():
            try:
                # Decode content
                if isinstance(content, bytes):
                    text = content.decode("utf-8")
                else:
                    text = content

                # Apply inline formatting conversion (XLIFF <bx>/<ex> → HTML)
                text = self.epub_applier.convert_xliff_to_html(text)

                # Apply translations if segment IDs are present in content
                text = self._apply_segments_to_xhtml(text, xliff_segments, options)

                # Encode back
                modified[file_path] = text.encode("utf-8")

            except Exception as e:
                logger.warning(f"Failed to process {file_path}: {e}")
                # Keep original content on error
                modified[file_path] = content if isinstance(content, bytes) else content.encode("utf-8")

        return modified

    def _find_xhtml_files(self, files: dict[str, bytes]) -> dict[str, bytes]:
        """Find XHTML files in EPUB contents.

        Args:
            files: Dict of file paths to contents.

        Returns:
            Dict of XHTML file paths to contents.
        """
        xhtml_files = {}

        for path in files:
            path_lower = path.lower()
            # Check for EPUB content directories
            for content_prefix in EPUB_CONTENT_PATHS:
                if content_prefix.lower() in path_lower:
                    if path_lower.endswith(XHTML_EXTENSIONS):
                        xhtml_files[path] = files[path]
                        break

        # If no prefixed files found, look for any XHTML in the archive
        if not xhtml_files:
            for path in files:
                if path.lower().endswith(XHTML_EXTENSIONS):
                    xhtml_files[path] = files[path]

        return xhtml_files

    def _apply_segments_to_xhtml(
        self,
        xhtml_content: str,
        segments: dict[str, str],
        options: ConverterOptions | None = None,
    ) -> str:
        """Apply translated segments to XHTML content.

        A1.3-followup (BeautifulSoup variant): parse the chapter XHTML
        once, mutate in place via a single BS4 pass that scans each
        element for matching id/data-segment/name attributes, serialize
        once. Replaces the O(N × M × 3) regex loop (segments × full
        chapter × 3 patterns) with O(N + M) where M is the chapter size.
        """
        if not segments:
            return xhtml_content

        soup = BeautifulSoup(xhtml_content, "html.parser")

        target_ids = set(segments.keys())

        for element in soup.find_all(True):
            element_id = element.get("id")
            if element_id and element_id in target_ids:
                self._replace_element_text(element, segments[element_id])
                target_ids.discard(element_id)
                continue
            data_seg = element.get("data-segment")
            if data_seg and data_seg in target_ids:
                self._replace_element_text(element, segments[data_seg])
                target_ids.discard(data_seg)
                continue
            name_attr = element.get("name")
            if name_attr and name_attr in target_ids:
                self._replace_element_text(element, segments[name_attr])
                target_ids.discard(name_attr)

            if not target_ids:
                break  # All segments applied.

        return str(soup)

    def _replace_element_text(self, element, translated_text: str) -> None:
        """Replace the text content of a BS4 element with the sanitized translation.

        Mirrors the regex replacement's behavior: drop existing children
        and insert the sanitized translation as the only text content.
        """
        element.clear()
        element.append(self._sanitize_text(translated_text))

    def _sanitize_text(self, text: str) -> str:
        """Sanitize text for XML insertion.

        Args:
            text: Raw text content.

        Returns:
            Sanitized text safe for XML.
        """
        # Basic XML escaping
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        return text

    def _repack_epub(self, files: dict[str, bytes], output_path: Path) -> None:
        """Repack EPUB contents into a new ZIP file.

        Args:
            files: Dict of file paths to contents.
            output_path: Path to write the EPUB file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, content in files.items():
                zf.writestr(name, content)

        logger.info(f"EPUB repacked to: {output_path}")

    def inject_images(
        self,
        epub_path: Path | str,
        images: list[ImagePlacement],
        output_path: Path | str,
    ) -> tuple[list[ImagePlacement], list[ImagePlacement]]:
        """Inject images into EPUB at specified spine positions.

        Args:
            epub_path: Path to EPUB file.
            images: List of ImagePlacement objects from OPP.
            output_path: Path to write the output EPUB.

        Returns:
            Tuple of (injected_images, orphaned_images).
        """
        epub_path = Path(epub_path)
        output_path = Path(output_path)

        orphaned: list[ImagePlacement] = []
        injected: list[ImagePlacement] = []

        positioned = [img for img in images if img.spine_index is not None]
        unpositioned = [img for img in images if img.spine_index is None]

        if unpositioned:
            for img in unpositioned:
                logger.warning(
                    "Image has no spine_index, appending to end: mime_type=%s",
                    img.mime_type,
                )
            orphaned.extend(unpositioned)

        if not positioned:
            if images:
                with zipfile.ZipFile(epub_path, "r") as zf_in:
                    for item in zf_in.namelist():
                        SkeletonLoader._validate_zip_entry_name(item)
                    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf_out:
                        for item in zf_in.namelist():
                            zf_out.writestr(item, zf_in.read(item))
            return (injected, orphaned)

        try:
            files = self._load_epub_skeleton(epub_path)
        except Exception as e:
            logger.error("Failed to load EPUB for image injection: %s", e)
            orphaned.extend(images)
            return (injected, orphaned)

        xhtml_files = self._find_xhtml_files(files)
        xhtml_paths = sorted(xhtml_files.keys())

        img_by_spine: dict[int, list[ImagePlacement]] = {}
        for img in positioned:
            idx = img.spine_index
            assert idx is not None, "positioned images must have spine_index"
            if idx not in img_by_spine:
                img_by_spine[idx] = []
            img_by_spine[idx].append(img)

        for spine_idx, imgs in img_by_spine.items():
            if spine_idx < 0 or spine_idx >= len(xhtml_paths):
                logger.warning(
                    "spine_index %d out of range, %d chapters available",
                    spine_idx,
                    len(xhtml_paths),
                )
                orphaned.extend(imgs)
                continue

            chapter_path = xhtml_paths[spine_idx]
            chapter_content = xhtml_files[chapter_path]
            if isinstance(chapter_content, bytes):
                chapter_content = chapter_content.decode("utf-8")

            soup = BeautifulSoup(chapter_content, "html.parser")

            for img in imgs:
                try:
                    img_bytes = self._get_image_bytes(img)
                    ext_map = {
                        "image/png": ".png",
                        "image/jpeg": ".jpg",
                        "image/gif": ".gif",
                    }
                    ext = ext_map.get(img.mime_type, ".png")
                    md5_hash = hashlib.md5(img_bytes).hexdigest()
                    img_name = f"image_{md5_hash[:8]}{ext}"
                    img_path = f"OEBPS/images/{img_name}"

                    if img_path not in files:
                        files[img_path] = img_bytes

                    data_uri = f"../images/{img_name}"
                    new_tag = soup.new_tag("img", src=data_uri)
                    if img.width:
                        new_tag["width"] = img.width
                    if img.height:
                        new_tag["height"] = img.height

                    body = soup.find("body")
                    if body:
                        body.append(new_tag)
                    else:
                        soup.append(new_tag)

                    files[chapter_path] = str(soup).encode("utf-8")
                    injected.append(img)
                    logger.debug(
                        "Injected image at spine %d: %s",
                        spine_idx,
                        img.mime_type,
                    )
                except Exception as e:
                    logger.error("Failed to inject image: %s", e)
                    orphaned.append(img)

        self._repack_epub(files, output_path)

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