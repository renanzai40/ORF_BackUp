"""Format Detection Engine for ORF Phase 2.

Detects document format using a priority chain:
1. manifest.json (from OPP) - explicit format field
2. Magic bytes - binary signatures in file header
3. Extension fallback - file extension matching

Raises FormatDetectionError when detection fails at all stages.
"""

from __future__ import annotations

from pathlib import Path

from orf.error_handlers.conversion_error import FormatDetectionError
from orf.logging import get_logger
from orf.parsers.manifest import find_manifest, parse_manifest

from orf.detection.magic_bytes import MAGIC_SIGNATURES

logger = get_logger("detection.format_detector")

# File extension to format mapping for fallback
EXTENSION_MAP: dict[str, str] = {
    ".pdf": "PDF",
    ".docx": "DOCX",
    ".pptx": "PPTX",
    ".odt": "ODT",
    ".epub": "EPUB",
    ".rtf": "RTF",
    ".html": "HTML",
    ".htm": "HTML",
    ".md": "MD",
    ".markdown": "MD",
}


class FormatDetector:
    """Detects document format via manifest, magic bytes, or extension.

    Usage:
        detector = FormatDetector()
        fmt = detector.detect("document.md")
        fmt = detector.detect_from_file("document.docx")
        fmt = detector.detect_from_manifest("document_manifest.json")
    """

    def detect_from_manifest(self, manifest_path: Path | str) -> str:
        """Detect format from manifest.json source information.

        Args:
            manifest_path: Path to manifest.json

        Returns:
            Format name string (e.g., "DOCX", "PDF")

        Raises:
            FormatDetectionError: If manifest cannot be parsed or lacks format
        """
        manifest_path = Path(manifest_path)

        try:
            manifest = parse_manifest(manifest_path)
        except Exception as e:
            raise FormatDetectionError(
                str(manifest_path), f"Failed to parse manifest: {e}"
            )

        detected_format = manifest.source.format.upper()

        if not detected_format:
            raise FormatDetectionError(
                str(manifest_path), "No format field in manifest source"
            )

        logger.debug("Detected format '%s' from manifest '%s'", detected_format, manifest_path)
        return detected_format

    def detect_from_file(self, file_path: Path | str) -> str:
        """Detect format by reading magic bytes from file header.

        Args:
            file_path: Path to file to inspect

        Returns:
            Format name string (e.g., "DOCX", "PDF")

        Raises:
            FormatDetectionError: If file cannot be read or signature unknown
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FormatDetectionError(str(file_path), "File does not exist")

        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
        except OSError as e:
            raise FormatDetectionError(str(file_path), f"Cannot read file: {e}")

        for fmt_name, magic in MAGIC_SIGNATURES.items():
            if header.startswith(magic):
                logger.debug("Detected format '%s' via magic bytes in '%s'", fmt_name, file_path)
                return fmt_name

        raise FormatDetectionError(
            str(file_path), "Unknown file format (no magic bytes match)"
        )

    def detect(self, file_path: Path | str) -> str:
        """Detect format using priority chain: manifest -> magic bytes -> extension.

        Args:
            file_path: Path to file to detect

        Returns:
            Format name string (e.g., "DOCX", "PDF")

        Raises:
            FormatDetectionError: If all detection methods fail
        """
        file_path = Path(file_path)

        # 1. Try manifest.json first
        manifest_path = find_manifest(file_path)
        if manifest_path is not None:
            try:
                return self.detect_from_manifest(manifest_path)
            except FormatDetectionError:
                logger.debug("Manifest detection failed for '%s', trying next method", file_path)

        # 2. Try magic bytes
        if file_path.exists() and not file_path.is_dir():
            try:
                return self.detect_from_file(file_path)
            except FormatDetectionError:
                logger.debug("Magic bytes detection failed for '%s', trying extension fallback", file_path)

        # 3. Extension fallback
        ext = file_path.suffix.lower()
        if ext in EXTENSION_MAP:
            fmt = EXTENSION_MAP[ext]
            logger.debug("Detected format '%s' via extension fallback for '%s'", fmt, file_path)
            return fmt

        raise FormatDetectionError(
            str(file_path),
            f"Cannot detect format: no manifest, magic bytes unknown, unknown extension '{ext}'"
        )