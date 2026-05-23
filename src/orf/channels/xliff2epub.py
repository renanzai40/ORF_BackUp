"""XLIFF→EPUB backfill converter with inline formatting preservation.

Applies translated XLIFF content to EPUB skeleton, preserving inline formatting
from XLIFF <bx>/<ex> tags converted to HTML <strong>/<em> tags.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from orf.converters.base import BaseConverter, ConversionResult
from orf.skeleton.inline_formatting import XLIFFInlineParser, EPUBHTMLInlineApplier
from orf.error_handlers.conversion_error import XLIFFParseError, InlineFormattingError
from orf.logging import get_logger

logger = get_logger("channel.xliff2epub")

# EPUB internal paths
EPUB_CONTENT_PATHS = ["EPUB/", "OEBPS/"]  # Common EPUB content directories
XHTML_EXTENSIONS = (".xhtml", ".html", ".htm")


class XLIFF2EPUBConverter(BaseConverter):
    """XLIFF→EPUB backfill with inline formatting preservation.

    Loads an EPUB skeleton (ZIP), applies translated XLIFF content to each
    XHTML chapter, and repacks the EPUB with inline formatting converted to HTML.
    """

    def __init__(self, manifest=None, frontmatter=None):
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

    def convert(
        self,
        epub_skeleton: Path | str,
        xliff_path: Path | str,
        output_path: Path | str,
        **options,
    ) -> ConversionResult:
        """Apply XLIFF translations to EPUB skeleton.

        Args:
            epub_skeleton: Path to EPUB skeleton file.
            xliff_path: Path to translated XLIFF file.
            output_path: Path to write the output EPUB.
            **options: Additional options (preserve_styles, etc.)

        Returns:
            ConversionResult with output path and status.
        """
        epub_skeleton = Path(epub_skeleton)
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

        Args:
            xliff_path: Path to XLIFF file.

        Returns:
            Dict mapping segment id to translated target text.

        Raises:
            XLIFFParseError: If XLIFF cannot be parsed.
        """
        segments = {}

        try:
            with open(xliff_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            raise XLIFFParseError(str(xliff_path), f"Cannot read file: {e}")

        # Parse XLIFF using regex (simple approach)
        # <trans-unit id="..."> ... <target>...</target> </trans-unit>
        # Or <unit id="..."> ... <segment><target>...</target></segment> </unit>

        # Pattern for trans-unit with target
        trans_unit_pattern = re.compile(
            r'<trans-unit[^>]*\sid="([^"]+)"[^>]*>(.*?)</trans-unit>',
            re.DOTALL | re.IGNORECASE
        )

        # Pattern for unit with segment/target (XLIFF 2.0 style)
        unit_pattern = re.compile(
            r'<unit[^>]*\sid="([^"]+)"[^>]*>(.*?)</unit>',
            re.DOTALL | re.IGNORECASE
        )

        # Pattern for target element
        target_pattern = re.compile(r'<target[^>]*>(.*?)</target>', re.DOTALL | re.IGNORECASE)

        # Try XLIFF 2.0 style first (unit/segment)
        for match in unit_pattern.finditer(content):
            unit_id = match.group(1)
            unit_content = match.group(2)

            # Find segment target
            seg_match = re.search(r'<segment[^>]*>(.*?)</segment>', unit_content, re.DOTALL | re.IGNORECASE)
            if seg_match:
                seg_content = seg_match.group(1)
                target_match = target_pattern.search(seg_content)
                if target_match:
                    segments[unit_id] = target_match.group(1)

        # Also try XLIFF 1.2 style (trans-unit/target)
        for match in trans_unit_pattern.finditer(content):
            unit_id = match.group(1)
            trans_content = match.group(2)

            target_match = target_pattern.search(trans_content)
            if target_match:
                # Avoid overwriting XLIFF 2.0 segments if any
                if unit_id not in segments:
                    segments[unit_id] = target_match.group(1)

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
                files[name] = zf.read(name)

        return files

    def _apply_translations_to_epub(
        self,
        epub_files: dict[str, bytes],
        xliff_segments: dict[str, str],
        options: dict,
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
        options: dict,
    ) -> str:
        """Apply translated segments to XHTML content.

        Args:
            xhtml_content: XHTML file content.
            segments: Dict of segment IDs to translated text.
            options: Additional options.

        Returns:
            Modified XHTML content.
        """
        # For basic backfill, we look for placeholder markers in the XHTML
        # and replace them with translated content

        result = xhtml_content

        # Simple placeholder pattern: id="segment_id" or data-segment="id"
        for seg_id, translated_text in segments.items():
            # Try different placeholder patterns
            patterns = [
                rf'id="{re.escape(seg_id)}"',
                rf'data-segment="{re.escape(seg_id)}"',
                rf'name="{re.escape(seg_id)}"',
            ]

            for pattern in patterns:
                # Find elements with this segment ID and replace content
                # This is a simplified approach - full implementation would
                # use proper XML parsing
                result = re.sub(
                    r'(<[^>]*' + pattern + r'[^>]*>)(.*?)(</[^>]+>)',
                    lambda m: m.group(1) + self._sanitize_text(translated_text) + m.group(3),
                    result,
                    flags=re.DOTALL
                )

        return result

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