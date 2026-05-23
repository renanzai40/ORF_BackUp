"""Magic bytes signatures for binary format detection.

Maps format names to their binary file signatures (magic bytes).
Also provides MIME type mapping.
"""

from __future__ import annotations

# Magic bytes signatures: format name -> magic bytes prefix
MAGIC_SIGNATURES: dict[str, bytes] = {
    "PDF": b"%PDF",
    "DOCX": b"PK\x03\x04",
    "PPTX": b"PK\x03\x04",
    "ODT": b"PK\x03\x04",
    "EPUB": b"PK\x03\x04",
    "RTF": b"{\\rtf",
    "HTML": b"<!DOCTYPE",
}

# MIME type mapping: format name -> MIME type string
MIME_TYPES: dict[str, str] = {
    "PDF": "application/pdf",
    "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "PPTX": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "ODT": "application/vnd.oasis.opendocument.text",
    "EPUB": "application/epub+zip",
    "RTF": "application/rtf",
    "HTML": "text/html",
    "MD": "text/markdown",
}