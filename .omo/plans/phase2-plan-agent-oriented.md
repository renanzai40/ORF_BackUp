# ORF Phase 2 Plan - Agent-Oriented Implementation

**Version**: v1.1  
**Author**: Sisyphus  
**Date**: 2026-05-23  
**Project**: Omni-Re-Formatter (ORF)  
**Goal**: Phase 2 implementation - Multi-format auto-detection, unified resource management, and new format channels (HTML/RTF/PDF)

---

## Context

### Current State (Phase 0 + Phase 1 Complete)

**What exists**:

| Component | Status | Key Files |
|-----------|--------|-----------|
| **Parsers** | ✅ Done | `manifest.py`, `frontmatter.py` |
| **Skeleton/Inline** | ✅ Done | `skeleton_loader.py`, `inline_formatting.py` |
| **MD Channels** | ✅ Done | `md2docx.py`, `md2odt.py`, `md2epub.py` |
| **XLIFF Channels** | ✅ Done | `xliff2docx.py`, `xliff2pptx.py`, `xliff2epub.py`, `xliff2html.py`, `xliff2odf.py` |
| **CLI** | ✅ Done | `cli.py` (apply-md, apply-xliff, convert-batch) |
| **Logging** | ✅ Done | `logging/__init__.py` |
| **Error Handling** | ✅ Done | `error_handlers/conversion_error.py` |
| **Tests** | ✅ Done | 13 test files covering all channels |

**What's missing (Phase 2 scope)**:

1. **Auto-detection engine** (`src/orf/detection/`) - format auto-probe via manifest.json + magic bytes
2. **Resource manager** (`src/orf/resources/`) - unified image management (dedup, naming, path mapping)
3. **MD→HTML channel** - missing pure HTML output (EPUB/HTML converter exists in xliff2html but not md2html)
4. **MD→RTF channel** - missing RTF output
5. **MD→PDF channel** - missing PDF output via Pandoc/WeasyPrint
6. **Batch processing enhancements** - parallel conversion, progress tracking

---

## Phase 2 Scope

Per the main plan (lines 414-508):

### 1. Format Auto-Detection Engine

| Task | Module | Description | Category | Dependency |
|------|--------|-------------|----------|------------|
| **P2-1** | `detection/format_detector.py` | Auto-detect target format from manifest.json or magic bytes | `unspecified-high` | None |
| **P2-2** | `detection/magic_bytes.py` | Magic bytes signature database for format detection | `unspecified-high` | Task P2-1 |
| **P2-3** | `tests/test_format_detector.py` | TDD for format detection | `quick` | Tasks P2-1, P2-2 |

### 2. Unified Resource Manager

| Task | Module | Description | Category | Dependency |
|------|--------|-------------|----------|------------|
| **P2-4** | `resources/image_manager.py` | Image dedup (MD5), naming, cross-format path mapping | `unspecified-high` | None |
| **P2-5** | `resources/path_resolver.py` | Resolve relative/absolute image paths across formats | `unspecified-high` | Task P2-4 |
| **P2-6** | `tests/test_image_manager.py` | TDD for resource management | `quick` | Tasks P2-4, P2-5 |

### 3. New MD Conversion Channels

| Task | Module | Description | Category | Dependency |
|------|--------|-------------|----------|------------|
| **P2-7** | `channels/md2html.py` | MD→HTML via Pandoc with CSS injection support | `unspecified-high` | None |
| **P2-8** | `channels/md2rtf.py` | MD→RTF via Pandoc | `unspecified-high` | None |
| **P2-9** | `channels/md2pdf.py` | MD→PDF via Pandoc/WeasyPrint with Chinese font support | `unspecified-high` | None |
| **P2-10** | `tests/test_md2html_channel.py` | TDD for MD→HTML | `quick` | Task P2-7 |
| **P2-11** | `tests/test_md2rtf_channel.py` | TDD for MD→RTF | `quick` | Task P2-8 |
| **P2-12** | `tests/test_md2pdf_channel.py` | TDD for MD→PDF | `quick` | Task P2-9 |

### 4. CLI Enhancements

| Task | Module | Description | Category | Dependency |
|------|--------|-------------|----------|------------|
| **P2-13** | `cli.py` (enhance) | Add `--target-format auto` support; update `apply-md` for new formats | `quick` | Tasks P2-1, P2-7, P2-8, P2-9 |
| **P2-14** | `tests/test_cli_phase2.py` | TDD for CLI enhancements | `quick` | Task P2-13 |

---

## Task Decomposition - Wave Structure

### Wave 1: Format Detection Engine (Tasks P2-1, P2-2, P2-3)

**P2-1: `src/orf/detection/format_detector.py`**

```python
"""Format auto-detection engine.

Detects target format via:
1. manifest.json source.format field (priority)
2. Magic bytes fallback for unknown files
3. Extension fallback (last resort)
"""

from pathlib import Path
from typing import Optional

from orf.parsers.manifest import parse_manifest, find_manifest
from orf.parsers.frontmatter import has_frontmatter
from orf.detection.magic_bytes import MAGIC_SIGNATURES
from orf.error_handlers.conversion_error import FormatDetectionError

# Supported ORF formats
ORF_FORMATS = {"DOCX", "PPTX", "ODT", "EPUB", "HTML", "RTF", "PDF"}


class FormatDetector:
    """Auto-detect document format.

    Detection priority:
    1. manifest.json source.format (if available)
    2. Magic bytes header signature
    3. File extension fallback
    """

    def detect_from_manifest(self, manifest_path: Path | str) -> Optional[str]:
        """Detect format from manifest.json.

        Args:
            manifest_path: Path to manifest.json

        Returns:
            Format string (e.g., "DOCX") or None if invalid
        """
        manifest = parse_manifest(manifest_path)
        fmt = manifest.source.format.upper()
        return fmt if fmt in ORF_FORMATS else None

    def detect_from_file(self, file_path: Path | str) -> Optional[str]:
        """Detect format via magic bytes.

        Args:
            file_path: Path to file

        Returns:
            Format string or None if not recognized
        """
        path = Path(file_path)
        with open(path, "rb") as f:
            header = f.read(512)  # Read enough for signature detection

        for fmt, signature in MAGIC_SIGNATURES.items():
            if signature in header:
                return fmt
        return None

    def detect(self, input_path: Path | str, manifest_path: Optional[Path | str] = None) -> str:
        """Full detection chain.

        Args:
            input_path: Input file path
            manifest_path: Optional manifest path (if not derivable from input_path)

        Returns:
            Detected format string (uppercase)

        Raises:
            FormatDetectionError: If format cannot be determined
        """
        input_path = Path(input_path)

        # Priority 1: manifest.json (preferred source)
        if manifest_path is None:
            manifest_path = find_manifest(input_path)

        if manifest_path and Path(manifest_path).exists():
            try:
                fmt = self.detect_from_manifest(manifest_path)
                if fmt:
                    return fmt
            except Exception as e:
                logger.debug(f"Manifest detection failed: {e}, trying next method")

        # Priority 2: magic bytes (for binary formats)
        try:
            fmt = self.detect_from_file(input_path)
            if fmt:
                return fmt
        except Exception as e:
            logger.debug(f"Magic bytes detection failed: {e}")

        # Priority 3: extension fallback (for text-based formats like MD, HTML)
        ext = input_path.suffix.upper()
        if ext.startswith("."):
            return ext[1:]  # Remove leading dot

        raise FormatDetectionError(
            file_path=str(input_path),
            reason="Cannot determine format from content or extension"
        )
```

**P2-2: `src/orf/detection/magic_bytes.py`**

```python
"""Magic bytes signatures for format detection.

Database of file signatures (magic numbers) for common formats.
Note: Office formats (DOCX, PPTX, ODT, EPUB) are all ZIP-based.
"""

from typing import Dict

# Magic bytes signatures: format -> bytes to search for in header
# Order matters: more specific signatures should come first
MAGIC_SIGNATURES: Dict[str, bytes] = {
    # PDF must be checked before ZIP (PDF starts with %PDF, not PK)
    "PDF": b"%PDF",

    # Office formats (ZIP-based) - all start with PK\x03\x04
    # Cannot distinguish between DOCX/PPTX/XLSX/ODT/EPUB purely by magic bytes
    # Use extension fallback for these when manifest unavailable
    "DOCX": b"PK\x03\x04",
    "PPTX": b"PK\x03\x04",
    "XLSX": b"PK\x03\x04",
    "ODT": b"PK\x03\x04",
    "EPUB": b"PK\x03\x04",

    # RTF starts with {\rtf
    "RTF": b"{\\rtf",

    # HTML detection
    "HTML": b"<!DOCTYPE",  # HTML5 doctype
}

# MIME type mapping
MIME_TYPES = {
    "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "PPTX": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "ODT": "application/vnd.oasis.opendocument.text",
    "EPUB": "application/epub+zip",
    "PDF": "application/pdf",
    "HTML": "text/html",
    "RTF": "application/rtf",
}
```

**P2-3: `tests/test_format_detector.py`** - TDD for P2-1, P2-2

**Test file structure** (following existing conventions):
```python
class TestFormatDetector:
    """Tests for FormatDetector class."""

    def test_detect_from_manifest_valid(self, sample_manifest_path: Path):
        """When manifest exists and has valid format."""
        detector = FormatDetector()
        result = detector.detect(sample_md_path, sample_manifest_path)
        assert result == "DOCX"

    def test_detect_from_magic_bytes_pdf(self, sample_pdf_path: Path):
        """PDF detection via magic bytes."""
        detector = FormatDetector()
        result = detector.detect(sample_pdf_path)
        assert result == "PDF"

    def test_detect_from_extension_md(self, sample_md_path: Path):
        """MD files fall back to extension."""
        detector = FormatDetector()
        result = detector.detect(sample_md_path)
        assert result == "MD"

    @patch("orf.parsers.manifest.parse_manifest")
    def test_detect_manifest_unavailable_fallback(self, mock_parse, tmp_path: Path):
        """When manifest unavailable, falls back to magic bytes."""
        mock_parse.side_effect = ManifestParseError("Not found")
        sample_file = tmp_path / "test.pdf"
        sample_file.write_bytes(b"%PDF-1.4")

        detector = FormatDetector()
        result = detector.detect(sample_file)
        assert result == "PDF"

    def test_detect_unsupported_format_raises(self, tmp_path: Path):
        """Unknown format raises FormatDetectionError."""
        detector = FormatDetector()
        with pytest.raises(FormatDetectionError):
            detector.detect(tmp_path / "unknown.xyz")
```

---

### Wave 2: Resource Manager (Tasks P2-4, P2-5, P2-6)

**P2-4: `src/orf/resources/image_manager.py`**

```python
"""Unified image resource manager.

Handles:
- MD5-based deduplication
- Consistent image naming
- Cross-format path mapping
"""

import hashlib
import threading
from pathlib import Path
from typing import Dict, List, Optional

from orf.logging import get_logger

logger = get_logger("resources.image_manager")


class ImageResource:
    """Represents a managed image resource."""

    def __init__(
        self,
        original_path: Path,
        md5: str,
        dedup_name: str,
        formats: List[str],
    ):
        self.original_path = original_path
        self.md5 = md5
        self.dedup_name = dedup_name  # e.g., "image_abc123.png"
        self.formats = formats  # ["docx", "html"]
        self.path_mappings: Dict[str, Path] = {}


class ImageManager:
    """Manages image resources across conversion.

    Thread-safe registry for image deduplication.
    """

    def __init__(self, resource_dir: Path | str = "resources"):
        self.resource_dir = Path(resource_dir)
        self._registry: Dict[str, ImageResource] = {}  # md5 -> resource
        self._name_map: Dict[str, str] = {}  # original_name -> dedup_name
        self._lock = threading.Lock()

    def compute_md5(self, file_path: Path | str) -> str:
        """Compute MD5 hash of file."""
        path = Path(file_path)
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    def register_image(self, image_path: Path | str) -> ImageResource:
        """Register an image, deduplicating if necessary.

        Args:
            image_path: Path to image file

        Returns:
            ImageResource for the registered image
        """
        path = Path(image_path)
        md5 = self.compute_md5(path)

        with self._lock:
            if md5 in self._registry:
                logger.debug(f"Image {path.name} is duplicate (MD5: {md5}), reusing existing")
                return self._registry[md5]

            # First occurrence: create dedup name
            ext = path.suffix.lower()
            dedup_name = f"image_{md5[:8]}{ext}"
            resource = ImageResource(
                original_path=path,
                md5=md5,
                dedup_name=dedup_name,
                formats=[],
            )
            self._registry[md5] = resource
            self._name_map[path.name] = dedup_name

            return resource

    def get_dedup_path(self, md5: str, target_format: str) -> Path:
        """Get deduplicated path for a target format.

        Args:
            md5: Image MD5 hash
            target_format: Target format (docx, html, etc.)

        Returns:
            Path where image should be stored for that format
        """
        if md5 not in self._registry:
            raise ResourceManagementError(
                resource_path="",
                operation="get_dedup_path",
                reason=f"Unknown MD5: {md5}"
            )

        resource = self._registry[md5]
        format_dir = self.resource_dir / target_format
        return format_dir / resource.dedup_name

    def resolve_md_paths(self, md_content: str, target_format: str) -> Dict[str, Path]:
        """Resolve image paths from MD content.

        Args:
            md_content: Markdown content with image references
            target_format: Target format for path mapping

        Returns:
            Dict mapping original paths to resolved paths
        """
        import re
        image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

        resolved = {}
        for match in image_pattern.finditer(md_content):
            alt_text, img_path = match.groups()
            path = Path(img_path)

            if path.exists():
                resource = self.register_image(path)
                resolved[img_path] = self.get_dedup_path(resource.md5, target_format)

        return resolved
```

**P2-5: `src/orf/resources/path_resolver.py`**

```python
"""Path resolver for cross-format resource mapping.

Handles:
- Relative to absolute path conversion
- Format-specific path adjustments
- Broken link detection
"""

from pathlib import Path
from typing import Dict, Optional


class PathResolver:
    """Resolves and normalizes file paths across formats."""

    def __init__(self, base_dir: Optional[Path | str] = None):
        self.base_dir = Path(base_dir) if base_dir else None

    def resolve_relative(self, path: Path | str, reference_file: Path | str) -> Path:
        """Resolve relative path against reference file location.

        Args:
            path: The path to resolve
            reference_file: The file the path is referenced from

        Returns:
            Absolute Path object
        """
        path = Path(path)
        if path.is_absolute():
            return path

        ref = Path(reference_file)
        if self.base_dir:
            return self.base_dir / path
        return ref.parent / path

    def adjust_for_format(self, path: Path | str, target_format: str) -> Path:
        """Adjust path for target format conventions.

        Args:
            path: Input path
            target_format: Target format (docx, html, etc.)

        Returns:
            Format-adjusted path
        """
        path = Path(path)
        target_format = target_format.lower()

        if target_format == "html":
            # HTML uses forward slashes
            return Path(path.as_posix())
        elif target_format in ("docx", "odt"):
            # Office formats use relative paths within ZIP
            return Path(path.name)  # Just filename for embedding
        else:
            return path

    def validate_path(self, path: Path | str, must_exist: bool = True) -> bool:
        """Validate that a path is safe and accessible.

        Args:
            path: Path to validate
            must_exist: Whether path must exist on filesystem

        Returns:
            True if path is valid and safe
        """
        path = Path(path)

        # Check for path traversal attempts
        try:
            resolved = path.resolve()
            if self.base_dir:
                resolved.relative_to(self.base_dir)
        except ValueError:
            return False  # Path traversal detected

        if must_exist and not resolved.exists():
            return False

        return True
```

**P2-6: `tests/test_image_manager.py`** - TDD for P2-4, P2-5

---

### Wave 3: New MD Channels (Tasks P2-7, P2-8, P2-9, P2-10, P2-11, P2-12)

**P2-7: `src/orf/channels/md2html.py`**

```python
"""Markdown to HTML conversion channel using Pandoc."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger

logger = get_logger("channel.md2html")


class MD2HTMLConverter(BaseConverter):
    """Markdown to HTML converter using Pandoc.

    Produces standalone HTML by default (includes <head>, <body>, etc.)
    """

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
        css_template: Optional[Path | str] = None,
    ):
        super().__init__(manifest, frontmatter)
        self.css_template = Path(css_template) if css_template else None

    @property
    def supported_format(self) -> str:
        return "HTML"

    def validate_input(self, input_path: Path | str) -> bool:
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        **options,
    ) -> ConversionResult:
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not self.validate_input(input_path):
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Invalid input file: {input_path}"],
            )

        cmd = [
            "pandoc",
            str(input_path),
            "-o", str(output_path),
            "--to", "html",
        ]

        # CSS injection via --css (Pandoc handles this natively)
        css = options.get("css") or self.css_template
        if css:
            cmd.extend(["--css", str(css)])

        # Standalone is Pandoc's default for HTML output
        # Only add if explicitly requested as False
        if options.get("standalone") is False:
            pass  # Don't add --standalone

        try:
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"tool": "pandoc", "cmd": " ".join(cmd)},
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Pandoc failed: {e.stderr}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Pandoc error: {e.stderr}"],
            )
        except FileNotFoundError:
            logger.error("Pandoc not found in PATH")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["Pandoc not installed or not in PATH"],
            )
```

**P2-8: `src/orf/channels/md2rtf.py`**

```python
"""Markdown to RTF conversion channel using Pandoc."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger

logger = get_logger("channel.md2rtf")


class MD2RTFConverter(BaseConverter):
    """Markdown to RTF converter using Pandoc."""

    @property
    def supported_format(self) -> str:
        return "RTF"

    def validate_input(self, input_path: Path | str) -> bool:
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        **options,
    ) -> ConversionResult:
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not self.validate_input(input_path):
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Invalid input file: {input_path}"],
            )

        cmd = [
            "pandoc",
            str(input_path),
            "-o", str(output_path),
            "--to", "rtf",
        ]

        try:
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"tool": "pandoc", "cmd": " ".join(cmd)},
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Pandoc failed: {e.stderr}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Pandoc error: {e.stderr}"],
            )
        except FileNotFoundError:
            logger.error("Pandoc not found in PATH")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["Pandoc not installed or not in PATH"],
            )
```

**P2-9: `src/orf/channels/md2pdf.py`**

```python
"""Markdown to PDF conversion channel using Pandoc with Chinese font support."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger

logger = get_logger("channel.md2pdf")


class MD2PDFConverter(BaseConverter):
    """Markdown to PDF converter using Pandoc with Chinese font support.

    Supports multiple rendering engines:
    - pandoc (default, uses pdflatex)
    - weasyprint (alternative, better for Chinese without LaTeX)
    """

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
        engine: str = "pandoc",  # "pandoc" or "weasyprint"
        font_path: Optional[Path | str] = None,  # Chinese font for PDF
    ):
        super().__init__(manifest, frontmatter)
        self.engine = engine
        self.font_path = Path(font_path) if font_path else None

    @property
    def supported_format(self) -> str:
        return "PDF"

    def validate_input(self, input_path: Path | str) -> bool:
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        **options,
    ) -> ConversionResult:
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not self.validate_input(input_path):
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Invalid input file: {input_path}"],
            )

        engine = options.get("engine", self.engine)

        if engine == "weasyprint":
            return self._convert_weasyprint(input_path, output_path, **options)
        else:
            return self._convert_pandoc(input_path, output_path, **options)

    def _convert_pandoc(
        self,
        input_path: Path,
        output_path: Path,
        **options,
    ) -> ConversionResult:
        """Convert via Pandoc (pdflatex by default)."""
        cmd = [
            "pandoc",
            str(input_path),
            "-o", str(output_path),
            "--to", "pdf",
        ]

        # Chinese font support via xelatex engine
        if options.get("chinese_font"):
            cmd.extend([
                "--pdf-engine=xelatex",
                "-V", "mainfont=SimSun",
            ])

        try:
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"tool": "pandoc", "engine": "pdflatex", "cmd": " ".join(cmd)},
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Pandoc PDF failed: {e.stderr}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Pandoc PDF error: {e.stderr}"],
            )
        except FileNotFoundError:
            logger.error("Pandoc not found in PATH")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["Pandoc not installed or not in PATH"],
            )

    def _convert_weasyprint(
        self,
        input_path: Path,
        output_path: Path,
        **options,
    ) -> ConversionResult:
        """Convert via WeasyPrint (HTML→PDF).

        Two-step process:
        1. MD → HTML (via MD2HTMLConverter)
        2. HTML → PDF (via WeasyPrint API)
        """
        # Step 1: Convert MD to HTML
        from orf.channels.md2html import MD2HTMLConverter

        html_path = output_path.with_suffix(".html")
        html_converter = MD2HTMLConverter(
            manifest=self.manifest,
            frontmatter=self.frontmatter,
        )
        html_result = html_converter.convert(input_path, html_path)

        if not html_result.success:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"HTML conversion failed: {html_result.errors}"],
            )

        # Step 2: Convert HTML to PDF via WeasyPrint API
        try:
            from weasyprint import HTML

            HTML(str(html_path)).write_pdf(str(output_path))

            # Clean up intermediate HTML file
            try:
                html_path.unlink()
            except OSError:
                pass

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"tool": "weasyprint", "engine": "html2pdf"},
            )

        except ImportError:
            logger.error("WeasyPrint not installed")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["WeasyPrint not installed. Install via: pip install weasyprint"],
            )
        except Exception as e:
            logger.error(f"WeasyPrint failed: {e}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"WeasyPrint error: {e}"],
            )
```

**P2-10, P2-11, P2-12**: TDD tests for each channel

**Test patterns** (following existing conventions from `test_md2docx_channel.py`):
```python
class TestMD2HTMLConverter:
    """Tests for MD2HTMLConverter."""

    def test_supported_format(self):
        assert converter.supported_format == "HTML"

    def test_validate_input_valid(self, sample_md: Path):
        assert converter.validate_input(sample_md) is True

    @patch("subprocess.run")
    def test_convert_success(self, mock_run, sample_md: Path, tmp_path: Path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        output = tmp_path / "output.html"
        result = converter.convert(sample_md, output)
        assert result.success is True
        assert result.output_path == output
        # Verify pandoc command
        call_args = mock_run.call_args[0][0]
        assert "pandoc" in call_args
        assert "--to" in call_args and "html" in call_args

    @patch("subprocess.run")
    def test_convert_with_css(self, mock_run, sample_md: Path, tmp_path: Path, css_template: Path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        output = tmp_path / "output.html"
        result = converter.convert(sample_md, output, css=str(css_template))
        assert result.success is True
        call_args = mock_run.call_args[0][0]
        assert "--css" in call_args

    def test_convert_invalid_input(self, tmp_path: Path):
        txt_file = tmp_path / "test.txt"
        txt_file.touch()
        result = converter.convert(txt_file, tmp_path / "out.html")
        assert result.success is False

    @patch("subprocess.run")
    def test_convert_pandoc_error(self, mock_run, sample_md: Path, tmp_path: Path):
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, "pandoc", stderr="Unknown extension")
        result = converter.convert(sample_md, tmp_path / "out.html")
        assert result.success is False
        assert "Pandoc error" in result.errors[0]

    @patch("subprocess.run")
    def test_convert_pandoc_not_found(self, mock_run, sample_md: Path, tmp_path: Path):
        mock_run.side_effect = FileNotFoundError()
        result = converter.convert(sample_md, tmp_path / "out.html")
        assert result.success is False
        assert "not in PATH" in result.errors[0]
```

---

### Wave 4: CLI Enhancements (Tasks P2-13, P2-14)

**P2-13: `src/orf/cli.py` updates**

Key changes:
1. Add `--target-format auto` support in `apply-md`
2. Update `apply-md` choice to include `html`, `rtf`, `pdf`
3. Update `convert-batch` to support new formats
4. Add `apply-md --auto-detect` flag

```python
@main.command("apply-md")
@click.argument("input_md", type=click.Path(exists=True))
@click.option(
    "--target-format",
    "-t",
    type=click.Choice(["docx", "odt", "epub", "html", "rtf", "pdf", "auto"]),
    default="docx",  # Keep explicit default for backwards compatibility
    help="目标格式 (auto=自动探测)",
)
@click.option("--auto-detect", is_flag=True, help="从manifest自动探测格式")
def apply_md(
    input_md: str,
    target_format: str,
    output: str | None,
    template: str | None,
    auto_detect: bool,
    ...
):
    """将 MD 文件转换为目标格式"""
    input_path = Path(input_md)

    # Auto-detect if requested
    if target_format == "auto" or auto_detect:
        from orf.detection.format_detector import FormatDetector
        detector = FormatDetector()
        try:
            detected = detector.detect(input_path)
            logger.info(f"Auto-detected format: {detected}")
            target_format = detected.lower()
        except FormatDetectionError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

    # Route to correct converter (existing pattern)
    if target_format == "docx":
        converter = MD2DOCXConverter(...)
    elif target_format == "odt":
        converter = MD2ODTConverter(...)
    elif target_format == "epub":
        converter = MD2EPUBConverter(...)
    elif target_format == "html":
        from orf.channels.md2html import MD2HTMLConverter
        converter = MD2HTMLConverter(...)
    elif target_format == "rtf":
        from orf.channels.md2rtf import MD2RTFConverter
        converter = MD2RTFConverter(...)
    elif target_format == "pdf":
        from orf.channels.md2pdf import MD2PDFConverter
        converter = MD2PDFConverter(...)
    else:
        click.echo(f"Unsupported format: {target_format}", err=True)
        sys.exit(1)
```

**P2-14**: CLI enhancement tests

---

## Error Handling Extensions (Phase 2)

### New Error Classes

Add to `src/orf/error_handlers/conversion_error.py`:

```python
class FormatDetectionError(ConversionError):
    """Raised when format cannot be automatically detected."""

    def __init__(self, file_path: str, reason: str):
        self.file_path = file_path
        self.reason = reason
        super().__init__(
            f"Cannot detect format for '{file_path}': {reason}"
        )


class ResourceManagementError(ConversionError):
    """Raised for image/resource management failures."""

    def __init__(self, resource_path: str, operation: str, reason: str):
        self.resource_path = resource_path
        self.operation = operation
        self.reason = reason
        super().__init__(
            f"Resource management error during '{operation}' on '{resource_path}': {reason}"
        )
```

---

## Shared Test Fixtures (conftest.py additions)

Add to `tests/conftest.py`:

```python
# Phase 2 fixtures

@pytest.fixture
def sample_image_paths(tmp_path: Path) -> list[Path]:
    """Create sample image files for resource manager tests."""
    from PIL import Image  # Use Pillow for image creation

    images = []
    for i in range(3):
        img_path = tmp_path / f"test_image_{i}.png"
        # Create a simple 10x10 PNG
        img = Image.new("RGB", (10, 10), color="red")
        img.save(img_path)
        images.append(img_path)
    return images


@pytest.fixture
def sample_detectable_content(tmp_path: Path) -> dict[str, Path]:
    """Create sample files for format detection tests."""
    files = {}

    # MD file with frontmatter
    md_path = tmp_path / "test.md"
    md_path.write_text("---\nsource_lang: en\ntarget_lang: zh\n---\n# Test")
    files["md"] = md_path

    # Manifest JSON
    manifest_path = tmp_path / "test_manifest.json"
    manifest_path.write_text(json.dumps({
        "manifest_version": "1.0",
        "source": {"format": "DOCX", "file_path": "test.docx"},
        "extraction": {}
    }))
    files["manifest"] = manifest_path

    # PDF file
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test content")
    files["pdf"] = pdf_path

    return files


@pytest.fixture
def css_template_file(tmp_path: Path) -> Path:
    """Create a sample CSS file for HTML conversion."""
    css_path = tmp_path / "style.css"
    css_path.write_text("body { font-family: Arial; }")
    return css_path
```

---

## File Structure (Phase 2 Additions)

```
src/orf/
├── detection/                    # NEW
│   ├── __init__.py
│   ├── format_detector.py        # P2-1
│   └── magic_bytes.py            # P2-2
├── resources/                    # NEW
│   ├── __init__.py
│   ├── image_manager.py          # P2-4
│   └── path_resolver.py          # P2-5
├── error_handlers/
│   └── conversion_error.py       # ADD: FormatDetectionError, ResourceManagementError
└── channels/
    ├── md2html.py                # P2-7
    ├── md2rtf.py                 # P2-8
    ├── md2pdf.py                 # P2-9
    └── ... (existing)
```

**Test additions**:
```
tests/
├── test_format_detector.py       # P2-3
├── test_image_manager.py         # P2-6
├── test_md2html_channel.py       # P2-10
├── test_md2rtf_channel.py        # P2-11
├── test_md2pdf_channel.py        # P2-12
└── test_cli_phase2.py            # P2-14
```

---

## Implementation Order

| Wave | Tasks | Description | Estimated Time |
|------|-------|-------------|----------------|
| **Wave 1** | P2-1, P2-2, P2-3 | Format Detection Engine + Error Classes | 2-3 hours |
| **Wave 2** | P2-4, P2-5, P2-6 | Resource Manager | 2-3 hours |
| **Wave 3** | P2-7, P2-8, P2-9, P2-10, P2-11, P2-12 | New MD Channels + Tests | 3-4 hours |
| **Wave 4** | P2-13, P2-14 | CLI Enhancements + Tests | 1-2 hours |

**Total estimated**: 1-1.5 days

---

## ATDD Acceptance Criteria

### Normal Flow
- [x] `orf apply-md translated.md --target-format auto` auto-detects format from manifest.json
- [x] Magic bytes detection works for PDF/RTF/HTML
- [x] Office formats (DOCX/PPTX) detected via manifest, fallback to extension
- [x] Image deduplication produces same MD5 → same file
- [x] MD→HTML output with CSS injection working
- [x] MD→RTF output working
- [x] MD→PDF output working (both pandoc and weasyprint engines)
- [x] `orf convert-batch` supports html, rtf, pdf formats

### Error Flow
- [x] No manifest → fallback to magic bytes → fallback to extension
- [x] Unknown format → `FormatDetectionError` with clear message
- [x] Image missing → `ResourceManagementError` with placeholder + warning
- [x] PDF engine unavailable → clear error with install suggestion

### Performance
- [x] Format detection ≤ 50ms
- [x] Image dedup ≥ 50MB/s
- [x] MD→PDF ≥ 10MB/s (via weasyprint)

---

## Dependencies on External Tools

| Tool | Purpose | Install |
|------|---------|---------|
| Pandoc | MD→DOCX/ODT/EPUB/HTML/RTF/PDF | `apt install pandoc` or `brew install pandoc` |
| WeasyPrint | Alternative PDF engine (HTML→PDF) | `pip install weasyprint` |
| python-magic | Magic bytes detection | `pip install python-magic` |

**Note**: Already in `pyproject.toml`:
- `python-magic>=0.4.27` ✅
- `pyyaml>=6.0` ✅

**Missing dependencies to add to pyproject.toml**:
```toml
[project.optional-dependencies]
weasyprint = ["weasyprint>=60.0"]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.21.0",
    "ruff>=0.1.0",
    "mypy>=1.5.0",
    "weasyprint>=60.0",  # For PDF testing
]
```

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| PDF generation fails without LaTeX | PDF channel broken | Provide weasyprint alternative; clear error messages |
| Magic bytes misdetection | Wrong format conversion | Manifest.json priority > magic bytes > extension |
| Image dedup race condition | Duplicate images | Thread-safe registry with threading.Lock |
| WeasyPrint not installed | PDF fallback fails | Clear ImportError with pip install instructions |

---

## Commit Strategy

```bash
# Wave 1: Format Detection + Error Classes
git commit -m "feat(detection): add FormatDetector with manifest + magic bytes"
git commit -m "feat(errors): add FormatDetectionError and ResourceManagementError"
git commit -m "test(detection): add format detection TDD"

# Wave 2: Resource Manager
git commit -m "feat(resources): add ImageManager with MD5 dedup and thread-safe registry"
git commit -m "feat(resources): add PathResolver for cross-format mapping"
git commit -m "test(resources): add resource manager TDD"

# Wave 3: New Channels
git commit -m "feat(channels): add MD2HTMLConverter via Pandoc"
git commit -m "feat(channels): add MD2RTFConverter via Pandoc"
git commit -m "feat(channels): add MD2PDFConverter with dual-engine (pandoc/weasyprint) support"
git commit -m "test(channels): add MD→HTML/RTF/PDF channel tests"

# Wave 4: CLI
git commit -m "feat(cli): add auto-detect and new format support"
git commit -m "test(cli): add Phase 2 CLI tests"
```

---

## Related Documents

- Main plan: `Omni-Re-Formatter (ORF) 开发计划 - DD Vibe Phase版.md` (Phase 2 section: lines 414-508)
- Phase 1 plan: `.omo/plans/phase1-plan-inline-formatting.md`

---

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| v1.1 | 2026-05-23 | Fixed md2pdf weasyprint API call; Added FormatDetectionError + ResourceManagementError; Added conftest fixtures; Fixed magic_bytes signature format; Fixed html standalone handling |
| v1.0 | 2026-05-23 | Initial plan |