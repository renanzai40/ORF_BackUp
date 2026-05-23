"""ORF Format Detection Engine

Detects document formats via manifest metadata, magic bytes, and extension fallback.
Used during Phase 2 to identify input format before conversion.

Priority chain:
1. manifest.json (from OPP) - explicit format field
2. Magic bytes - binary signatures in file header
3. Extension fallback - file extension matching
"""

from __future__ import annotations

from orf.detection.magic_bytes import MAGIC_SIGNATURES, MIME_TYPES
from orf.detection.format_detector import FormatDetector

__all__ = [
    "FormatDetector",
    "MAGIC_SIGNATURES",
    "MIME_TYPES",
]