"""FormatDetector tests."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from orf.detection.format_detector import FormatDetector, EXTENSION_MAP
from orf.error_handlers.conversion_error import FormatDetectionError
from orf.parsers.manifest import Manifest, ManifestSource


class TestFormatDetector:
    """Tests for FormatDetector format detection."""

    @pytest.fixture
    def detector(self) -> FormatDetector:
        return FormatDetector()

    @pytest.fixture
    def valid_manifest(self) -> Manifest:
        source = ManifestSource(
            file_path="/path/to/source.docx",
            original_filename="source.docx",
            format="DOCX",
            file_size_bytes=12345,
            file_hash_md5="abc123",
        )
        return MagicMock(
            spec=Manifest,
            source=source,
        )

    def test_detect_from_manifest_valid(self, detector: FormatDetector, valid_manifest: Manifest, tmp_path: Path):
        """Manifest with valid format returns format string."""
        manifest_path = tmp_path / "test_manifest.json"
        manifest_path.write_text("{}", encoding="utf-8")

        with patch("orf.detection.format_detector.parse_manifest") as mock_parse:
            mock_parse.return_value = valid_manifest
            result = detector.detect_from_manifest(manifest_path)
            assert result == "DOCX"

    def test_detect_from_manifest_invalid_format(self, detector: FormatDetector, tmp_path: Path):
        """Manifest with unknown format returns the format string (no validation)."""
        manifest_path = tmp_path / "test_manifest.json"
        manifest_path.write_text("{}", encoding="utf-8")

        with patch("orf.detection.format_detector.parse_manifest") as mock_parse:
            mock_parse.return_value = MagicMock(spec=Manifest, source=MagicMock(format="UNKNOWN_FORMAT"))
            result = detector.detect_from_manifest(manifest_path)
            assert result == "UNKNOWN_FORMAT"

    def test_detect_from_magic_bytes_pdf(self, detector: FormatDetector, tmp_path: Path):
        """PDF detected via magic bytes."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 test content" + b"\x00" * 100)

        result = detector.detect_from_file(pdf_file)
        assert result == "PDF"

    def test_detect_from_magic_bytes_rtf(self, detector: FormatDetector, tmp_path: Path):
        """RTF detected via magic bytes."""
        rtf_file = tmp_path / "test.rtf"
        rtf_file.write_bytes(b'{\\rtf1\\ansi{\\fonttbl{\\f0 Arial;}}}' + b"\x00" * 100)

        result = detector.detect_from_file(rtf_file)
        assert result == "RTF"

    def test_detect_from_extension_md(self, detector: FormatDetector, tmp_path: Path):
        """MD falls back to extension."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test content", encoding="utf-8")

        ext = md_file.suffix.lower()
        assert ext in EXTENSION_MAP
        result = detector.detect(md_file)
        assert result == "MD"

    def test_detect_extension_fallback(self, detector: FormatDetector, tmp_path: Path):
        """When no manifest and no magic bytes, use extension."""
        # File with no manifest nearby, no recognizable magic bytes, but has extension
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("plain text content", encoding="utf-8")

        # Since .txt is not in EXTENSION_MAP, it should raise
        with pytest.raises(FormatDetectionError):
            detector.detect(txt_file)

    def test_detect_unsupported_format_raises(self, detector: FormatDetector, tmp_path: Path):
        """Raises FormatDetectionError for unknown formats."""
        unknown_file = tmp_path / "test.unknown"
        unknown_file.write_bytes(b"\x00\x01\x02\x03\x04" + b"\xff" * 11)

        with pytest.raises(FormatDetectionError) as exc_info:
            detector.detect(unknown_file)
        assert "Cannot detect format" in str(exc_info.value)

    def test_detect_manifest_unavailable_fallback(self, detector: FormatDetector, tmp_path: Path):
        """Falls back to magic bytes when manifest fails."""
        # Create a file with no manifest nearby but with recognizable magic bytes
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 test content" + b"\x00" * 100)

        with patch("orf.detection.format_detector.find_manifest") as mock_find:
            mock_find.return_value = None  # No manifest found
            result = detector.detect(pdf_file)
            assert result == "PDF"